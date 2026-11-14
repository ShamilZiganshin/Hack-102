@echo off
chcp 65001 >nul
cd /d "%~dp0"
"%~dp0..\детекция масла\.venv\Scripts\python.exe" "%~dp0launch.py"
if errorlevel 1 pause
