#!/usr/bin/env python

import codecs
import os
import re
import sys
from datetime import datetime, timedelta, tzinfo
from glob import glob
try:
    from urllib import urlretrieve
    from urlparse import urljoin, urlparse
    import xml.etree.ElementTree as ET
except: # if Python 3
    from urllib.request import urlretrieve
    from urllib.parse import urljoin, urlparse
    # cElementTree is default in py3 but breaks namespace hack, so we have 
    # to use a workaround to use the pure Python version instead.
    from test.support import import_fresh_module
    ET = import_fresh_module('xml.etree.ElementTree', blocked=['_elementtree'])

import yaml
from bs4 import BeautifulSoup

from html2text import html2text_file


######################################################
# Configration
######################################################
config = yaml.load(codecs.open('config.yaml', 'r'))
source_dir = config['source_dir']
build_dir = config['build_dir']
download_images = config['download_images']
flat_output = config['flat_output']
item_type_filter = set(config['item_type_filter'])
item_field_filter = config['item_field_filter']
body_replace = config['body_replace']


# unicode support for both Py2 & Py3
def utf8(x):
    try:
        return unicode(x)
    except NameError:
        return str(x)

class ns_tracker_tree_builder(ET.XMLParser):
    
    def __init__(self, *args, **kwargs):
        ET.XMLParser.__init__(self)
        self._parser.StartNamespaceDeclHandler = self._start_ns
        self.namespaces = {}
    
    def _start_ns(self, prefix, ns):
        self.namespaces[prefix] = '{' + ns + '}'


def parse_xml(file):
    parser = ns_tracker_tree_builder()
    tree = ET.ElementTree()
    print('reading: ' + file)
    root = tree.parse(file, parser)
    ns = parser.namespaces
    ns[''] = ''

    c = root.find('channel')

    def parse_header():
        return {
            'title': utf8(c.find('title').text),
            'link': utf8(c.find('link').text),
            'description': utf8(c.find('description').text)
        }

    def parse_items():
        export_items = []
        xml_items = c.findall('item')
        for i in xml_items:

            def gi(q, unicode_wrap=True, empty=False):
                namespace = ''
                tag = ''
                if q.find(':') > 0:
                    namespace, tag = q.split(':', 1)
                else:
                    tag = q
                try:
                    result = i.find(ns[namespace] + tag).text
                except AttributeError:
                    result = 'No Content Found'
                    if empty:
                        result = ''
                if unicode_wrap:
                    result = utf8(result)
                return result

            body = gi('content:encoded')
            for key in body_replace:
                body = re.sub(key, body_replace[key], body)

            img_srcs = []
            if body is not None:
                try:
                    soup = BeautifulSoup(body, features="html5lib")
                    img_tags = soup.find_all('img')
                    for img in img_tags:
                        img_srcs.append(img['src'])
                except:
                    print('could not parse html: ' + body)
            # print(img_srcs)

            excerpt = gi('excerpt:encoded', empty=True)

            export_item = {
                'title': gi('title'),
                'link': gi('link'),
                'author': gi('dc:creator'),
                'date': gi('wp:post_date_gmt'),
                'slug': gi('wp:post_name'),
                'status': gi('wp:status'),
                'type': gi('wp:post_type'),
                'wp_id': gi('wp:post_id'),
                'parent': gi('wp:post_parent'),
                'comments': gi('wp:comment_status') == u'open',
                'body': body,
                'excerpt': excerpt,
                'img_srcs': img_srcs
            }

            export_items.append(export_item)

        return export_items

    return {
        'header': parse_header(),
        'items': parse_items(),
    }


def write_markdown(data):

    sys.stdout.write('writing...')
    item_uids = {}
    attachments = {}

    def get_blog_path(data):
        name = data['header']['title']
        name = re.sub('^https?', '', name)
        name = re.sub(':', ' -', name)
        name = re.sub('[^A-Za-z0-9 _.-]', '', name)
        return os.path.normpath(build_dir + '/' + name)

    blog_dir = get_blog_path(data)

    def get_full_dir(dir):
        full_dir = os.path.normpath(blog_dir + '/' + dir)
        if (not os.path.exists(full_dir)):
            os.makedirs(full_dir)
        return full_dir

    def get_item_uid(item, namespace=''):
        result = None
        if namespace not in item_uids:
            item_uids[namespace] = {}

        if item['wp_id'] in item_uids[namespace]:
            result = item_uids[namespace][item['wp_id']]
        else:
            uid = []
            s_title = item['slug']
            if s_title is None or s_title == '':
                s_title = item['title']
            if s_title is None or s_title == '':
                s_title = 'untitled'
            s_title = s_title.replace(' ', '_')
            s_title = re.sub('[^a-zA-Z0-9_-]', '', s_title)
            uid.append(s_title)
            fn = ''.join(uid)
            n = 1
            while fn in item_uids[namespace]:
                n = n + 1
                fn = ''.join(uid) + '_' + str(n)
                item_uids[namespace][i['wp_id']] = fn
            result = fn
        return result

    def get_item_path(item, dir=''):
        full_dir = get_full_dir(dir)
        filename_parts = [full_dir, '/']
        filename_parts.append(item['uid'])
        if item['type'] in ['page']:
            if (not os.path.exists(''.join(filename_parts))):
                os.makedirs(''.join(filename_parts))
            filename_parts.append('/index')
        filename_parts.append('.md')
        return ''.join(filename_parts)

    def get_attachment_path(src, dir, dir_prefix='images'):
        try:
            files = attachments[dir]
        except KeyError:
            attachments[dir] = files = {}

        try:
            filename = files[src]
        except KeyError:
            file_root, file_ext = os.path.splitext(os.path.basename(
                urlparse(src)[2]))
            file_infix = 1
            if file_root == '':
                file_root = '1'
            current_files = files.values()
            maybe_filename = file_root + file_ext
            while maybe_filename in current_files:
                maybe_filename = file_root + '-' + str(file_infix) + file_ext
                file_infix = file_infix + 1
            files[src] = filename = maybe_filename

        target_dir = os.path.normpath(blog_dir + '/' + dir_prefix + '/' + dir)
        target_file = os.path.normpath(target_dir + '/' + filename)

        if (not os.path.exists(target_dir)):
            os.makedirs(target_dir)

        return target_file

    for i in data['items']:

        for field, value in item_field_filter.items():
            if(i[field] == value):
                continue

        fn = None
        if i['type'] in item_type_filter:
            pass

        elif i['type'] in ['page', 'post', 'chapter', 'back-matter', 'front-matter']:
            i['uid'] = get_item_uid(i)
            parentpath = ''
            if flat_output == False:
                # Chase down parent path, if any
                item = i
                while item['parent'] != '0':
                    item = next((parent for parent in data['items']
                                 if parent['wp_id'] == item['parent']), None)
                    if item:
                        parentpath = get_item_uid(item) + '/' + parentpath
                    else:
                        break
            fn = get_item_path(i, parentpath)
            
        else:
            print('Unknown item type :: ' + i['type'])
            print(i)
            sys.exit()

        if download_images:
            for img in i['img_srcs']:
                try:
                    urlretrieve(urljoin(data['header']['link'],
                                        img.encode('utf-8')),
                                get_attachment_path(img, i['uid']))
                except:
                    print('\n unable to download ' + urljoin(
                        data['header']['link'], img.encode('utf-8')))

        filters = [
            [r'\n{3,10}', '\n\n'], # replaces large breaks between paragraphs with smaller ones
            [r'\n{2,10}#', '\n\n\n#'], # replaces large breaks between sections with smaller ones
            [r'\[caption\sid=([^]]+)]', ''], # removes useless '[caption id=]' tags
            [r'\[/caption\]', ''] # removes other half of '[caption id=]' tags
        ]

        if fn is not None and i['title'] != "Hello world!" and i['body'] != 'None':
            with codecs.open(fn, 'w', encoding='utf-8') as out:
                out.write('# {0}\n\n'.format(i['title']))
                try:
                    content = html2text_file(i['body'], None)
                    for f in filters:
                        search, replace = f
                        content = re.sub(search, replace, content)
                    out.write(content)
                except Exception as e:
                    print(e)
                    print('\n Parse error on: ' + i['title'])

    print('\n')


books = glob(source_dir + '/*.xml')
print('\n')
for book in books:
    data = parse_xml(book)
    write_markdown(data)

n = len(books)
print('{0} book{1} converted.\n'.format(n, '' if n==1 else 's'))
