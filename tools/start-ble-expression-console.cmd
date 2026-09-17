@echo off
setlocal
set "ROOT=%~dp0.."
set "PYTHON_EXE=%ROOT%\.venv-ble\Scripts\python.exe"

if not exist "%PYTHON_EXE%" (
    py -3 -m venv "%ROOT%\.venv-ble"
    if errorlevel 1 (
        echo Could not create the BLE Python environment.
        pause
        exit /b 1
    )
)

"%PYTHON_EXE%" -m pip install -r "%~dp0requirements-ble.txt"
if errorlevel 1 (
    echo Could not install Bleak.
    pause
    exit /b 1
)

"%PYTHON_EXE%" "%~dp0ble-expression-console.py" %*
set "EXIT_CODE=%ERRORLEVEL%"
pause
exit /b %EXIT_CODE%
