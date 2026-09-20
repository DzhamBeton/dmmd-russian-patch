@echo off
setlocal
cd /d "%~dp0"

where py.exe >nul 2>&1
if not errorlevel 1 goto use_py

where python.exe >nul 2>&1
if not errorlevel 1 goto use_python

echo.
echo Python 3 is required.
echo Download: https://www.python.org/downloads/windows/
echo Enable "Add Python to PATH" during installation.
echo.
pause
exit /b 1

:use_py
py.exe -3 "editor\server.py" "translations\translation.jsonl"
goto finished

:use_python
python.exe "editor\server.py" "translations\translation.jsonl"

:finished
if errorlevel 1 pause
endlocal
