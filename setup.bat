@echo off
setlocal EnableExtensions

cd /d "%~dp0"

echo.
echo  ClipMark setup
echo  --------------
echo.

where py >nul 2>nul
if %ERRORLEVEL%==0 (
    set "PYTHON=py -3"
) else (
    where python >nul 2>nul
    if %ERRORLEVEL%==0 (
        set "PYTHON=python"
    ) else (
        echo  Python 3 was not found.
        echo.
        echo  1. Download Python from https://www.python.org/downloads/
        echo  2. Run the installer
        echo  3. Check "Add python.exe to PATH"
        echo  4. Run this script again
        echo.
        pause
        exit /b 1
    )
)

echo  Using: %PYTHON%
%PYTHON% --version
if errorlevel 1 (
    echo  Could not run Python.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo.
    echo  Creating virtual environment...
    %PYTHON% -m venv .venv
    if errorlevel 1 (
        echo  Failed to create the virtual environment.
        pause
        exit /b 1
    )
)

echo.
echo  Installing dependencies...
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo.
    echo  Failed to install dependencies.
    pause
    exit /b 1
)

echo.
echo  Setup complete.
echo  Double-click run.bat or run:  run.bat
echo.
pause
