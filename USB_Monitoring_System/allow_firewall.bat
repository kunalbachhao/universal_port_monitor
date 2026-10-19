@echo off
rem Adds Windows Firewall rules so other laptops can reach the server:
rem   TCP 5000 = event connection,  UDP 5001 = automatic discovery
rem Needed on the SERVER laptop. Windows asks for administrator permission.
rem Rules work on any network type (phone hotspots are "Public") but only accept
rem devices on the same local subnet (remoteip=localsubnet), not the internet.
rem To remove them later:  allow_firewall.bat --remove

net session >nul 2>&1
if errorlevel 1 (
    echo Requesting administrator permission...
    if "%~1"=="" (
        powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs -Wait"
    ) else (
        powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList '%~1' -Verb RunAs -Wait"
    )
    exit /b
)

netsh advfirewall firewall delete rule name="USB Monitor TCP 5000" >nul 2>&1
netsh advfirewall firewall delete rule name="USB Monitor UDP 5001" >nul 2>&1

if /i "%~1"=="--remove" (
    echo Firewall rules removed.
) else (
    netsh advfirewall firewall add rule name="USB Monitor TCP 5000" dir=in action=allow protocol=TCP localport=5000 profile=any remoteip=localsubnet >nul
    netsh advfirewall firewall add rule name="USB Monitor UDP 5001" dir=in action=allow protocol=UDP localport=5001 profile=any remoteip=localsubnet >nul
    echo Firewall rules added: TCP 5000 and UDP 5001 ^(local network devices only^).
)
timeout /t 5
