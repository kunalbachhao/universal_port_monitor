@echo off
rem Double-click on the INVIGILATOR laptop to start the central server.
rem Extra options are passed through, e.g.:  start_server.bat --port 6000
cd /d "%~dp0"
title USB Monitoring SERVER
call scripts\find_python.bat
if not defined PY ( pause & exit /b 1 )
%PY% server\server.py %*
echo.
pause
