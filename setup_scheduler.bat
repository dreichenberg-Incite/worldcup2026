@echo off
echo ============================================
echo  FIFA World Cup 2026 - Scheduler Setup
echo ============================================
echo.

:: Find Python
where python >nul 2>&1
if %errorlevel% == 0 (
    set PYTHON=C:\Users\doron\AppData\Local\Microsoft\WindowsApps\python3.exe
)

echo Found Python: %PYTHON%
echo.

:: Install dependencies
echo Installing Python dependencies...
%PYTHON% -m pip install anthropic requests pytz
echo.

:: Get the script path
set SCRIPT=%~dp0generate_briefing.py
echo Script location: %SCRIPT%
echo.

:: Ask for API keys
echo ============================================
echo  STEP 1: Enter your API Keys
echo ============================================
echo.
echo Get your FREE football-data.org key at: https://www.football-data.org/client/register
echo Get your Anthropic key at: https://console.anthropic.com/
echo.
set /p FOOTBALL_KEY=Enter football-data.org API key:
set /p ANTHROPIC_KEY=Enter Anthropic API key:
echo.

:: Set environment variables system-wide so Task Scheduler can access them
echo Setting environment variables...
setx WC_FOOTBALL_API_KEY "%FOOTBALL_KEY%"
setx ANTHROPIC_API_KEY "%ANTHROPIC_KEY%"
echo Done. Environment variables set.
echo.

:: Create the scheduled task (7:00 AM ET every day, June-July 2026)
echo ============================================
echo  STEP 2: Creating Windows Scheduled Task
echo ============================================
echo.

:: Delete existing task if present
schtasks /delete /tn "WorldCup2026Briefing" /f >nul 2>&1

:: Create task: runs at 7:00 AM every day
schtasks /create /tn "WorldCup2026Briefing" /tr "\"C:\Program Files\Git\bin\bash.exe\" -c \"python3 '/c/Users/doron/OneDrive/Desktop/Claude Home Design/worldcup2026/generate_briefing.py'\"" /sc daily /st 07:00 /ru %USERNAME% /f

if %errorlevel% == 0 (
    echo.
    echo ✅ SUCCESS! Scheduled task created.
    echo.
    echo The briefing will auto-generate every morning at 7:00 AM ET
    echo and open in your browser automatically.
    echo.
    echo You can also run it manually anytime:
    echo   %PYTHON% "%SCRIPT%"
    echo.
    echo Or double-click: run_now.bat
) else (
    echo.
    echo ⚠️  Task creation failed. You may need to run this as Administrator.
    echo Right-click setup_scheduler.bat → Run as administrator
)

echo.
echo ============================================
echo Running once now to test...
echo ============================================
echo.
set WC_FOOTBALL_API_KEY=%FOOTBALL_KEY%
set ANTHROPIC_API_KEY=%ANTHROPIC_KEY%
%PYTHON% "%SCRIPT%"

pause
