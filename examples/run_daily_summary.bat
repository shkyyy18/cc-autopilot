@echo off
REM Example batch wrapper for daily_summary cron job
REM Replace paths with your actual installation directory

set SCRIPT_DIR=%~dp0
set PROJECT_ROOT=%SCRIPT_DIR%..

powershell -NoProfile -ExecutionPolicy Bypass -File "%PROJECT_ROOT%\src\run.ps1" -Prompt "%PROJECT_ROOT%\examples\daily_summary.txt" -Output "%PROJECT_ROOT%\logs\daily_summary.log" -TimeoutMin 30
