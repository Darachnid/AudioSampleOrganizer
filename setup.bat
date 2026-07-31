@echo off
setlocal EnableExtensions

cd /d "%~dp0"

echo.
echo  ClipMark Qt setup check
echo  -----------------------
echo.
echo  This app is now Qt 6 / C++.
echo  Build with CMake after installing Qt 6, CMake, and libsndfile.
echo.
echo  See README.md for Windows build steps.
echo.
where cmake >nul 2>nul
if errorlevel 1 (
    echo  cmake was not found on PATH.
) else (
    cmake --version
)

echo.
pause
