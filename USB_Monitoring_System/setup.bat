@echo off
rem ===================================================================
rem  ONE-TIME SETUP - double-click on every laptop (server and clients)
rem    1. checks Python
rem    2. creates the logs folder
rem    3. runs the self-test
rem    4. offers to add the Windows Firewall rules (asks for admin)
rem  Optional:  setup.bat --no-firewall   (skip step 4)
rem ===================================================================
cd /d "%~dp0"
title USB Monitoring System - Setup
echo ====================================================
echo   USB MONITORING SYSTEM - SETUP
echo ====================================================
echo.

echo [1/4] Checking Python...
call scripts\find_python.bat
if not defined PY (
    start "" https://www.python.org/downloads/
    echo  Opened the Python download page. Run setup.bat again after installing.
    pause
    exit /b 1
)
%PY% --version
echo  No extra packages needed - only the Python standard library is used.
echo.

echo [2/4] Preparing folders...
if not exist logs mkdir logs
if not exist logs\events.csv echo timestamp,pc_name,ip,event,drive> logs\events.csv
echo  logs\events.csv ready.
echo.

echo [3/4] Running self-test (about 10 seconds)...
%PY% -m unittest discover tests >"%TEMP%\usb_monitor_selftest.txt" 2>&1
if errorlevel 1 (
    type "%TEMP%\usb_monitor_selftest.txt"
    echo.
    echo  SELF-TEST FAILED - see the messages above.
    pause
    exit /b 1
)
echo  Self-test passed.
echo.

echo [4/4] Windows Firewall
if /i "%~1"=="--no-firewall" (
    echo  Skipped.
) else (
    echo  The SERVER laptop must allow incoming TCP 5000 and UDP 5001,
    echo  otherwise other laptops cannot connect.
    choice /c YN /m " Add the firewall rules now (Windows will ask for permission)"
    if not errorlevel 2 call allow_firewall.bat --from-setup
)
echo.
echo ====================================================
echo   SETUP COMPLETE
echo ====================================================
echo   Server laptop :  double-click start_server.bat
echo   Client laptops:  double-click start_client.bat
echo   (Clients find the server automatically on the same network.)
echo.
pause
