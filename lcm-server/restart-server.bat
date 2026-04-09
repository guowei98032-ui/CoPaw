@echo off
REM LCM Server Restart Script
REM This script stops any existing LCM server and starts a new one

echo ============================================================
echo LCM Server Restart
echo ============================================================
echo.

cd /d %~dp0

REM Step 1: Find and kill existing LCM server process
echo Step 1: Stopping existing LCM server...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :3721') do (
    echo   Found process PID %%a on port 3721
    taskkill /F /PID %%a
)

REM Wait a moment for port to be released
timeout /t 3 /nobreak >nul

REM Step 2: Start new server in background
echo.
echo Step 2: Starting LCM server...
echo.

start /B cmd /c "npx tsx index.js"

REM Wait longer for server to start
echo Waiting for server to start (10 seconds)...
timeout /t 10 /nobreak >nul

REM Step 3: Verify server is running with retries
echo.
echo Step 3: Verifying server...

set retry=0
:check_server
curl -s http://localhost:3721/health > temp_health.json 2>&1
if %errorlevel% equ 0 (
    python -m json.tool temp_health.json
    if %errorlevel% equ 0 (
        echo.
        echo ============================================================
        echo ✅ LCM Server started successfully!
        echo ============================================================
        echo.
        echo Server URL: http://localhost:3721
        echo Health Check: http://localhost:3721/health
        echo.
        del temp_health.json
        goto :success
    )
)

set /a retry+=1
if %retry% lss 3 (
    echo Retry %retry%/3...
    timeout /t 3 /nobreak >nul
    goto :check_server
)

echo.
echo ============================================================
echo ⚠️  Server may not have started properly
echo ============================================================
echo.
echo Please check if Node.js is installed and run:
echo   cd %~dp0
echo   npm start
echo.

:success
pause
