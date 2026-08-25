@echo off
rem CardGenerator -- stop a gallery server that has no window to Ctrl+C.
rem
rem You should not normally need this: serve.bat runs in the foreground and
rem Ctrl+C stops it. This exists for the state that made it necessary once --
rem a server started detached, with no terminal to interrupt, which otherwise
rem means Task Manager.
rem
rem Usage:  stop-server.bat [port]     (default 8765)
setlocal
set "PORT=%~1"
if "%PORT%"=="" set "PORT=8765"

set "FOUND="
for /f "tokens=5" %%P in ('netstat -ano -p tcp ^| findstr /r /c:"LISTENING" ^| findstr /r /c:":%PORT% "') do (
    if not "%%P"=="0" (
        echo Stopping PID %%P -- listening on 127.0.0.1:%PORT%
        taskkill /pid %%P /t /f >nul 2>&1
        set "FOUND=1"
    )
)

if not defined FOUND (
    echo Nothing is listening on port %PORT%.
    exit /b 1
)
echo Done.
