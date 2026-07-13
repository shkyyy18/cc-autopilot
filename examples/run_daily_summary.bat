@echo off
REM Copyable Windows wrapper for the supported AgentCron CLI example.
REM Install the package first: python -m pip install -e .

set "SCRIPT_DIR=%~dp0"
agentcron --config "%SCRIPT_DIR%agentcron.json" run daily-summary
exit /b %ERRORLEVEL%
