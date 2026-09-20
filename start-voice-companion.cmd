@echo off
setlocal
set "PYTHONUTF8=1"
cd /d "%~dp0"
set "COMPANION_PY=%~dp0Codex-Temp\.venv-companion\Scripts\python.exe"
if not exist "%COMPANION_PY%" (
  python -m venv "%~dp0Codex-Temp\.venv-companion"
  if errorlevel 1 goto failed
)
"%COMPANION_PY%" -c "import fastapi,uvicorn,httpx,bleak" >nul 2>nul
if errorlevel 1 (
  "%COMPANION_PY%" -m pip install -r "%~dp003-Src\stopwatch-voice-companion\requirements-lock.txt"
  if errorlevel 1 goto failed
)
"%COMPANION_PY%" "%~dp003-Src\stopwatch-voice-companion\run_companion.py"
if errorlevel 1 goto failed
exit /b 0
:failed
echo Companion did not start. Read the message above; no other service was stopped.
pause
exit /b 1
