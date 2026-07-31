@echo off
setlocal EnableExtensions

cd /d "%~dp0"

if exist "build\Release\ClipMark.exe" (
    start "" "build\Release\ClipMark.exe"
    exit /b 0
)

if exist "build\ClipMark.exe" (
    start "" "build\ClipMark.exe"
    exit /b 0
)

echo  ClipMark.exe not found.
echo  Build first:
echo    cmake -S . -B build
echo    cmake --build build --config Release
echo.
pause
exit /b 1
