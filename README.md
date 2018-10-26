PressBooks XML to Markdown Converter
====================================

A utility for converting books in PressBooks XML or WordPress XML format (as provided as a download option through the PressBooks web UI) to individual Markdown files for each chapter. Intended for converting open textbooks to Markdown from platforms that use PressBooks, such as [University of Minnesota Open Textbook
Library](https://www.lib.umn.edu/publishing/works/textbooks) and [BC
Open Textbooks](https://opentextbc.ca).

This tool is adapted from the
[exitwp](https://github.com/thomasf/exitwp) tool created by Thomas
Frössman.

Getting started
---------------

- [Download](https://github.com/a-hurst/PressBooks2md/archive/master.zip) the project and unzip it.
- Download one or more books in PressBooks or WordPress XML format (e.g. [this one](https://open.lib.umn.edu/psychologyresearchmethods/)) and place them in the `book-xml` folder.
- Run the converter by typing `python exitwp.py` in the console from
  the directory of the unzipped archive
- You should now have all the books converted into separate
  directories under the `build` directory

Requirements
------------
To install all the packages required to run the script, run

```
pip install --upgrade -r requirements.txt
```
in the root of the project folder.

This project reqires Python 2.7, or Python 3.3 or newer to run. 


Configuration
-------------

See the [configuration
file](https://github.com/a-hurst/PressBooks2md/blob/master/config.yaml) for all
configurable options.
