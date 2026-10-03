@echo off
title Browser Agent Server
echo Starting Browser Agent Web Server...
cd /d "%~dp0"
python web.py
pause
