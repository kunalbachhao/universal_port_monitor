@echo off
rem Double-click on each EXAM laptop to start USB monitoring.
rem The server is found automatically. Optional extras, e.g.:
rem     start_client.bat --name LAB-PC-01
rem     start_client.bat --server 192.168.1.100
cd /d "%~dp0"
title USB Monitoring CLIENT
call scripts\find_python.bat
if not defined PY ( pause & exit /b 1 )
%PY% client\client.py %*
echo.
pause
