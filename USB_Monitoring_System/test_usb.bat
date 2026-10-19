@echo off
rem Double-click, then plug in / remove a pen drive to check USB detection.
rem Works without the network or server. Close the window to stop.
cd /d "%~dp0"
title USB Monitoring - USB detection test
call scripts\find_python.bat
if not defined PY ( pause & exit /b 1 )
%PY% client\usb_monitor.py
echo.
pause
