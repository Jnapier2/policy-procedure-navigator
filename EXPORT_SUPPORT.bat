@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
call "%~dp0PolicyNavigator.bat" export
exit /b %ERRORLEVEL%
