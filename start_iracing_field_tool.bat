@echo off
setlocal

cd /d "%~dp0"
set "TOOL_PYTHON=%CD%\.venv\Scripts\python.exe"

if not exist "%TOOL_PYTHON%" (
    echo Creating the Python virtual environment...
    py -m venv .venv
    if errorlevel 1 goto :setup_error
)

"%TOOL_PYTHON%" -c "import flask, irsdk" >nul 2>&1
if errorlevel 1 (
    echo Installing required packages...
    "%TOOL_PYTHON%" -m pip install -r requirements.txt
    if errorlevel 1 goto :setup_error
)

if /i "%~1"=="--check" (
    echo iRacing Field Tool launcher is ready.
    endlocal
    exit /b 0
)

echo Starting the iRacing Field Tool...
start "iRacing Field Tool Server" cmd /k ""%TOOL_PYTHON%" "%CD%\app.py""

powershell.exe -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:5000'"

endlocal
exit /b 0

:setup_error
echo.
echo The iRacing Field Tool could not be started.
echo Review the error above, then press any key to close this window.
pause >nul
endlocal
exit /b 1
