@echo off
setlocal

set "PROJECT_DIR=D:\seemal\global-wildfire-v2"
set "LOGFILE=%PROJECT_DIR%\startup.log"

echo [%date% %time%] Startup triggered >> "%LOGFILE%"

cd /d "%PROJECT_DIR%"

:: Docker Desktop may still be launching at logon. Poll until the engine
:: answers, up to 2 minutes, before trying to bring the stack up.
set /a TRIES=0

:waitdocker
docker info <nul >nul 2>&1
if %errorlevel%==0 goto dockerready

set /a TRIES+=1
if %TRIES% geq 24 (
    echo [%date% %time%] Docker did not become ready in time, aborting. >> "%LOGFILE%"
    goto :eof
)
ping 127.0.0.1 -n 6 >nul
goto waitdocker

:dockerready
echo [%date% %time%] Docker is ready, starting the stack... >> "%LOGFILE%"
docker compose up -d <nul >> "%LOGFILE%" 2>&1

:: Give the frontend a few seconds to come up, then open the portal.
ping 127.0.0.1 -n 9 >nul
start "" "http://localhost:5180"

echo [%date% %time%] Done. >> "%LOGFILE%"
endlocal
