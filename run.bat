@echo off
setlocal EnableExtensions

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo  First-time setup required...
    call "%~dp0setup.bat"
    if errorlevel 1 exit /b 1
)

echo.
echo  Starting ClipMark...
echo  Use Command Prompt or Windows Terminal.
echo  When prompted, paste the full path to a WAV file.
echo.

".venv\Scripts\python.exe" -m ClipMark

if errorlevel 1 (
    echo.
    echo  ClipMark exited with an error.
    pause
)
