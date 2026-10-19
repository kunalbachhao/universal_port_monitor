@echo off
rem Sets PY to a working Python 3 command ("py -3" or "python").
rem Used by the .bat files in the project folder. Leaves PY empty if none found.
set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>nul && set "PY=py -3"
if defined PY exit /b 0
python -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" >nul 2>nul && set "PY=python"
if defined PY exit /b 0
echo.
echo  Python 3.8 or newer was not found on this PC.
echo  Install it from https://www.python.org/downloads/
echo  and tick "Add python.exe to PATH" during installation.
echo.
exit /b 1
