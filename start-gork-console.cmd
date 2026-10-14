@echo off
setlocal
set "ROOT=%~dp0"
set "APP_DIR=%ROOT%03-Src\gork-desktop"
set "ELECTRON_EXE=%APP_DIR%\node_modules\electron\dist\electron.exe"
if not exist "%ELECTRON_EXE%" (
  where node >nul 2>nul || (echo Node.js 24+ is required for the first installation.& pause & exit /b 1)
  pushd "%APP_DIR%"
  call npm install
  if errorlevel 1 (popd & echo Failed to install desktop dependencies.& pause & exit /b 1)
  popd
)
powershell.exe -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%ROOT%tools\gork-startup-preflight.ps1" -ProjectRoot "%ROOT%."
if errorlevel 1 (echo Gork startup check stopped. See the message above.& pause & exit /b 1)
start "" "%ELECTRON_EXE%" "%APP_DIR%"
if errorlevel 1 (echo Failed to start Gork Robot Console.& pause & exit /b 1)
exit /b 0
