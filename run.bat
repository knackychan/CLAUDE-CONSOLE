@echo off
rem Claude Console: the window, no console (errors go to %USERPROFILE%\.claude\console\window-errors.log)
cd /d "%~dp0"
start "" pythonw -m console
