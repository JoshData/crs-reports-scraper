crs-reports-scraper
===================

Downloads Congressional Research Service (CRS) reports from the CRS.gov website (which is only visible from within the U.S. Capitol computer network).

On a Windows computer, download one of the [WinPython Zero](https://winpython.github.io/) packages (we last used WinPython64-3.7.4.1Zero.exe) and run it to extract its contents anywhere, like the `WPy` directory in this folder. If you use a different path, edit the `start.bat` script in this directory so that the first line correctly reflects the location of the WinPython folder.

Double-click `start.bat` to run the main script. It will download the CRS reports and metadata into folders created in this directory.

Put `WPy\python-...\pythonw.exe crs_scraper.py` in the Start Menu to run the scraper regularly. Set the working directory to this directory.

To upload reports to Dropbox, create a file:

```
dropbox_access_token.txt
------------------------
TOKEN=dropbox access token generated at https://www.dropbox.com/developers/apps
PATH=/reports
```
