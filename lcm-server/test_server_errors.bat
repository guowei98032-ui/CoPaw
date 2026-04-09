@echo off
REM Test script to capture server console output and check for errors
cd /d %~dp0

echo ============================================================
echo LCM Server Error Capture Test
echo ============================================================
echo.

REM Start server and capture output to file
echo Starting server and capturing output...
echo.

REM Use timeout to run for 30 seconds then stop
start /B npx tsx index.js > server_output.log 2>&1
timeout /t 5 /nobreak >nul

REM Run a test that triggers compaction
echo Running compaction test...
python test_force_compact.py > test_output.log 2>&1

REM Wait for test to complete
timeout /t 2 /nobreak >nul

REM Stop server
taskkill /F /IM node.exe 2>nul
taskkill /F /IM tsx.exe 2>nul

REM Check for errors in server output
echo.
echo ============================================================
echo Server Console Output Analysis
echo ============================================================
echo.

echo Searching for errors in server_output.log...
echo.

findstr /C:"no summary model candidates" server_output.log >nul 2>&1
if %errorlevel% equ 0 (
    echo [ERROR] Found "no summary model candidates" error!
    echo.
    echo Full error context:
    findstr /C:"no summary model candidates" server_output.log
    echo.
) else (
    echo [OK] No "no summary model candidates" error found
)

findstr /C:"FALLING BACK TO EMERGENCY TRUNCATION" server_output.log >nul 2>&1
if %errorlevel% equ 0 (
    echo [ERROR] Found "FALLING BACK TO EMERGENCY TRUNCATION" error!
    echo.
    echo Full error context:
    findstr /C:"FALLING BACK TO EMERGENCY TRUNCATION" server_output.log
    echo.
) else (
    echo [OK] No "FALLING BACK TO EMERGENCY TRUNCATION" error found
)

findstr /C:"createLcmSummarizeFromLegacyParams returned undefined" server_output.log >nul 2>&1
if %errorlevel% equ 0 (
    echo [ERROR] Found "createLcmSummarizeFromLegacyParams returned undefined"!
    echo.
    echo Full error context:
    findstr /C:"createLcmSummarizeFromLegacyParams returned undefined" server_output.log
    echo.
) else (
    echo [OK] No "createLcmSummarizeFromLegacyParams returned undefined" error found
)

echo.
echo ============================================================
echo Last 50 lines of server output:
echo ============================================================
echo.

REM Show last 50 lines (PowerShell)
powershell -Command "Get-Content server_output.log -Tail 50"

echo.
echo ============================================================
echo Full log saved to: server_output.log
echo ============================================================
echo.

pause
