@echo off

REM EDIT THIS LINE DEPENDING ON WHERE WinPython IS INSTALLED.
set WP=.\WinPython-32bit-3.4.4.1Zero
REM THERE IS NOTHING ELSE TO CHANGE IN THIS FILE.

REM Must load Python environment before running pip.
call %WP%\scripts\env.bat

REM Check that Python modules are installed...
%WP%\python-3.4.4\Scripts\pip.exe install -r requirements.txt

REM Run the CRS scraper...
%WP%\python-3.4.4\python.exe crs_scraper.py
