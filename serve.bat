@echo off
rem CardGenerator -- start the local gallery in THIS terminal window.
rem
rem Home: the VS Code terminal panel, via Terminal > Run Task > "Gallery: serve"
rem (the default build task, so Ctrl+Shift+B runs it too). It stays in the
rem foreground, so Ctrl+C stops the server. Ctrl+C then asks "Terminate batch
rem job (Y/N)?" -- Python already had the signal by then, so the server is down
rem either way; Y just closes the script.
rem
rem Usage:  serve.bat [port]     (default 8765)
setlocal
cd /d "%~dp0"

set "PORT=%~1"
if "%PORT%"=="" set "PORT=8765"

rem Prefer a project venv over whatever `python` happens to be on PATH, so the
rem task cannot start against an interpreter that has no cardgen installed.
set "PY=python"
if exist "%~dp0.venv\Scripts\python.exe" set "PY=%~dp0.venv\Scripts\python.exe"

"%PY%" -c "import cardgen" 2>nul
if errorlevel 1 (
    echo.
    echo   cardgen is not importable by "%PY%".
    echo   Run:  "%PY%" -m pip install -e .
    echo.
    exit /b 1
)

title CardGenerator gallery :%PORT%
echo Gallery:  http://127.0.0.1:%PORT%/web/index.html
echo Stop it:  Ctrl+C in this terminal  (or stop-server.bat %PORT%)
echo.
"%PY%" -m cardgen.cli serve --port %PORT%
