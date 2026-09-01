@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
set "ROOT=%~dp0"
set "MODE=%~1"
if not defined MODE set "MODE=start"
title Policy and Procedure Navigator

if not exist "%ROOT%logs" mkdir "%ROOT%logs" >nul 2>&1
set "EARLY_LOG=%ROOT%logs\LATEST_LAUNCH_STATUS.txt"

echo ====================================================================
echo Policy and Procedure Navigator
echo Evidence-grounded policy answers and controlled workflows
echo ====================================================================
echo [INFO] Project folder: %ROOT%
echo [INFO] Launch mode: %MODE%
echo.

call :FIND_PYTHON
if errorlevel 1 goto :NO_PYTHON

if defined PY_LAUNCHER (
  py %PY_VERSION% "%ROOT%scripts\windows_launcher.py" "%MODE%"
) else (
  "%PY_EXE%" "%ROOT%scripts\windows_launcher.py" "%MODE%"
)
set "RC=%ERRORLEVEL%"

if not "%RC%"=="0" (
  echo.
  echo [ERROR] The launcher stopped with exit code %RC%.
  echo [INFO] The exact error is preserved in:
  echo        %ROOT%logs\launcher_latest.log
  echo        %ROOT%logs\LATEST_LAUNCH_STATUS.txt
  echo.
  pause
  exit /b %RC%
)

if /I not "%MODE%"=="start" (
  echo.
  echo [DONE] %MODE% completed successfully.
  pause
)
exit /b 0

:FIND_PYTHON
set "PY_LAUNCHER="
set "PY_VERSION="
set "PY_EXE="

py -3.13 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
if not errorlevel 1 (
  set "PY_LAUNCHER=1"
  set "PY_VERSION=-3.13"
  exit /b 0
)
py -3.12 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
if not errorlevel 1 (
  set "PY_LAUNCHER=1"
  set "PY_VERSION=-3.12"
  exit /b 0
)
py -3.11 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
if not errorlevel 1 (
  set "PY_LAUNCHER=1"
  set "PY_VERSION=-3.11"
  exit /b 0
)
py -3.14 -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
if not errorlevel 1 (
  set "PY_LAUNCHER=1"
  set "PY_VERSION=-3.14"
  exit /b 0
)

call :TRY_PYTHON_PATH "%LocalAppData%\Programs\Python\Python313\python.exe"
if defined PY_EXE exit /b 0
call :TRY_PYTHON_PATH "%LocalAppData%\Programs\Python\Python312\python.exe"
if defined PY_EXE exit /b 0
call :TRY_PYTHON_PATH "%LocalAppData%\Programs\Python\Python311\python.exe"
if defined PY_EXE exit /b 0
call :TRY_PYTHON_PATH "%LocalAppData%\Programs\Python\Python314\python.exe"
if defined PY_EXE exit /b 0
call :TRY_PYTHON_PATH "%ProgramFiles%\Python313\python.exe"
if defined PY_EXE exit /b 0
call :TRY_PYTHON_PATH "%ProgramFiles%\Python312\python.exe"
if defined PY_EXE exit /b 0
call :TRY_PYTHON_PATH "%ProgramFiles%\Python311\python.exe"
if defined PY_EXE exit /b 0
call :TRY_PYTHON_PATH "%ProgramFiles%\Python314\python.exe"
if defined PY_EXE exit /b 0

for /f "delims=" %%P in ('where python 2^>nul') do call :TRY_PYTHON_PATH "%%P"
if defined PY_EXE exit /b 0
for /f "delims=" %%P in ('where python3 2^>nul') do call :TRY_PYTHON_PATH "%%P"
if defined PY_EXE exit /b 0
exit /b 1

:TRY_PYTHON_PATH
set "CANDIDATE=%~1"
if /I not "%CANDIDATE:\WindowsApps\=%"=="%CANDIDATE%" exit /b 0
if not exist "%CANDIDATE%" exit /b 0
"%CANDIDATE%" -c "import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)" >nul 2>&1
if not errorlevel 1 set "PY_EXE=%CANDIDATE%"
exit /b 0

:NO_PYTHON
>"%EARLY_LOG%" echo {
>>"%EARLY_LOG%" echo   "ok": false,
>>"%EARLY_LOG%" echo   "stage": "python_not_found",
>>"%EARLY_LOG%" echo   "message": "Python 3.11 or newer was not found.",
>>"%EARLY_LOG%" echo   "project_root": "%ROOT:\=\\%"
>>"%EARLY_LOG%" echo }
echo [ERROR] Python 3.11 or newer was not found.
echo [INFO] Install 64-bit Python with the Python launcher enabled, then run this file again.
echo [INFO] No application data or supported local settings were changed.
echo [INFO] Status file: %EARLY_LOG%
echo.
pause
exit /b 2
