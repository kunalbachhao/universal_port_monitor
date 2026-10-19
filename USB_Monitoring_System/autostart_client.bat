@echo off
rem Makes the USB client start automatically when this user logs in to Windows.
rem Use only on lab PCs, with permission, after everything else works.
rem     autostart_client.bat            -> turn ON
rem     autostart_client.bat --remove   -> turn OFF
set "LAUNCHER=%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\USB_Monitor_Client.bat"

if /i "%~1"=="--remove" (
    if exist "%LAUNCHER%" del "%LAUNCHER%"
    echo Auto-start turned OFF.
) else (
    > "%LAUNCHER%" echo @echo off
    >>"%LAUNCHER%" echo start "USB Monitoring CLIENT" /min "%~dp0start_client.bat"
    echo Auto-start turned ON. The client will start minimised at every login.
    echo Startup file: %LAUNCHER%
)
timeout /t 5
