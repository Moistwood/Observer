@echo off
cd /d "%~dp0"
py -3.13 app.py
if errorlevel 1 pause
