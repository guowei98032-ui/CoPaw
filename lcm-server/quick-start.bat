@echo off
REM Quick start script for LCM server with summary model fix
REM Usage: quick-start.bat

echo ============================================================
echo LCM Server Quick Start
echo ============================================================
echo.

cd /d %~dp0

echo Step 1: Checking configuration...
node test_summary_config.js
if errorlevel 1 (
    echo.
    echo ERROR: Configuration test failed. Please fix issues above.
    pause
    exit /b 1
)

echo.
echo Step 2: Starting LCM server...
echo.
echo Press Ctrl+C to stop the server
echo.

REM Start server with tsx
npx tsx index.js

pause
