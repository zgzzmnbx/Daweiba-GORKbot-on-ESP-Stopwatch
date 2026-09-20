@echo off
setlocal
chcp 65001 >nul
set "PYTHONUTF8=1"
cd /d "%~dp0"
set "AUDIO_PY=Codex-Temp\.venv-companion\Scripts\python.exe"
if not exist "%AUDIO_PY%" (
    echo Please run start-voice-companion.cmd once to install the project environment.
    pause
    exit /b 1
)
if "%~1"=="" (
    echo StopWatch Settings - Audio test. Close other BLE controller connections.
    echo Echo test: hold A on the device to record, release A to finish. B stops.
    "%AUDIO_PY%" tools\stopwatch_audio.py echo
) else (
    "%AUDIO_PY%" tools\stopwatch_audio.py %*
)
set "AUDIO_RESULT=%ERRORLEVEL%"
pause
exit /b %AUDIO_RESULT%
