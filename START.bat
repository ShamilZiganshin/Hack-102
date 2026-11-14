@echo off
cd /d "%~dp0"
py -3.11 bootstrap.py
if errorlevel 1 pause
