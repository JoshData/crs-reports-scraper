@echo off

REM Run this script to start the scraper in the foreground, and on first use to
REM install Python package dependencies.

REM EDIT THIS LINE DEPENDING ON WHERE WinPython IS INSTALLED.
set WP=.\WinPython-32bit-3.4.4.1Zero\python-3.4.4
REM THERE IS NOTHING ELSE TO CHANGE IN THIS FILE.

REM Must load Python environment before running pip.
call %WP%\..\scripts\env.bat

REM Check that Python modules are installed...
%WP%\Scripts\pip.exe install -r requirements.txt

REM Run the CRS scraper...
%WP%\python.exe crs_scraper.py
