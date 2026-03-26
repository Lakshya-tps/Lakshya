@echo off
setlocal enabledelayedexpansion

REM Resets ONLY the admin database so a fresh admin can be registered/approved again.
REM Close the Secure Identity Server before running this (the DB may be locked).

cd /d "%~dp0"

set "DB_DIR=%CD%\database"
set "ADMIN_DB=%DB_DIR%\admins.db"

echo === Reset Admin Data ===
echo Target: "%ADMIN_DB%"
echo.

if not exist "%DB_DIR%" (
  echo Database folder not found: "%DB_DIR%"
  echo Nothing to reset.
  exit /b 0
)

REM Remove sqlite db + possible journal/WAL files.
for %%F in ("%ADMIN_DB%" "%ADMIN_DB%-journal" "%ADMIN_DB%-wal" "%ADMIN_DB%-shm") do (
  if exist "%%~fF" (
    del /f /q "%%~fF" 2>nul
  )
)

if exist "%ADMIN_DB%" (
  echo Failed to delete "%ADMIN_DB%".
  echo Make sure the Flask server is stopped, then run again.
  exit /b 1
)

echo Admin database reset complete.
echo Next: start the stack again (e.g. "..\start_secure_identity_stack.bat").
exit /b 0

