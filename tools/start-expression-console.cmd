@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0stopwatch-expression-console.ps1"
if errorlevel 1 pause
