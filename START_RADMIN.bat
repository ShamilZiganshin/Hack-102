@echo off
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0START_RADMIN.ps1" %*
if errorlevel 1 pause
