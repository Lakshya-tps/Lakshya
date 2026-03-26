@echo off
setlocal EnableExtensions EnableDelayedExpansion

cd /d "%~dp0"

set "LOG_FILE=%~dp0server-5055.log"
set "POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"

if not exist "%~dp0.venv\Scripts\activate.bat" (
  echo Virtualenv not found: "%~dp0.venv\Scripts\activate.bat"
  echo Create it and install deps:
  echo   python -m venv .venv
  echo   .venv\Scripts\python.exe -m pip install -r requirements.txt
  exit /b 1
)

call "%~dp0.venv\Scripts\activate.bat"

if not defined HOST set "HOST=127.0.0.1"
if not defined PORT set "PORT=5055"
if not defined DEBUG set "DEBUG=0"

rem Normalize env values (trim quotes/whitespace) to avoid getaddrinfo failures due to invisible trailing spaces.
call :normalize_var HOST
call :normalize_var PORT
call :normalize_var DEBUG

rem Treat empty-but-defined values as unset.
if "!HOST!"=="" set "HOST=127.0.0.1"
if "!PORT!"=="" set "PORT=5055"
if "!DEBUG!"=="" set "DEBUG=0"

rem If PORT is not numeric after normalization, fall back to 5055.
echo(!PORT!| %SystemRoot%\System32\findstr.exe /r "^[0-9][0-9]*$" >nul
if errorlevel 1 set "PORT=5055"

echo.>>"%LOG_FILE%"
echo ===== Secure Identity Server start %date% %time% =====>>"%LOG_FILE%"
echo CWD=%CD%>>"%LOG_FILE%"
echo HOST=%HOST% PORT=%PORT% DEBUG=%DEBUG%>>"%LOG_FILE%"
echo Python:>>"%LOG_FILE%"
python -c "import sys; print(sys.executable)" >>"%LOG_FILE%" 2>&1
python -c "import os; print('ENV_HOST_REPR=', repr(os.getenv('HOST'))); print('ENV_PORT_REPR=', repr(os.getenv('PORT'))); print('ENV_DEBUG_REPR=', repr(os.getenv('DEBUG')))" >>"%LOG_FILE%" 2>&1

echo Starting Secure Identity Server on http://%HOST%:%PORT% ...
echo Logging to: "%LOG_FILE%"
echo (Close this window to stop the server.)
echo.

if exist "%POWERSHELL%" (
  rem Run through PowerShell so we can stream output to console + append to the log.
  rem `*>&1` merges all PowerShell streams into stdout, so native stderr won't surface as NativeCommandError records.
  "%POWERSHELL%" -NoProfile -Command "& python backend\app.py *>&1 | Tee-Object -FilePath '%LOG_FILE%' -Append; exit $LASTEXITCODE"
  set "EXIT_CODE=%ERRORLEVEL%"
) else (
  python backend\app.py >>"%LOG_FILE%" 2>&1
  set "EXIT_CODE=%ERRORLEVEL%"
)

echo.
echo Server crashed or exited (code %EXIT_CODE%). Check: "%LOG_FILE%"
exit /b %EXIT_CODE%

:normalize_var
set "VAR=%~1"
set "VAL=!%VAR%!"
set "VAL=!VAL:"=!"
for /f "tokens=* delims= " %%A in ("!VAL!") do set "VAL=%%A"
:trim_tail
if "!VAL:~-1!"==" " (
  set "VAL=!VAL:~0,-1!"
  goto :trim_tail
)
set "%VAR%=!VAL!"
exit /b 0
