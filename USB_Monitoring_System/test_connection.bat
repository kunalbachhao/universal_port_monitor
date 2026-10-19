@echo off
rem Double-click on a CLIENT laptop while the server is running.
rem Sends "Hello from examination PC" to the server and reports success.
cd /d "%~dp0"
title USB Monitoring - Connection test
call scripts\find_python.bat
if not defined PY ( pause & exit /b 1 )
%PY% client\client.py --test %*
echo.
pause
