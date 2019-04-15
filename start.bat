@echo off

REM Run this script to start the scraper in the foreground, and on first use to
REM install Python package dependencies.

REM EDIT THIS LINE DEPENDING ON WHERE WinPython IS INSTALLED.
call WPy\scripts\env.bat

REM Check that Python modules are installed...
pip install -r requirements.txt

REM Run the CRS scraper...
python crs_scraper.py
