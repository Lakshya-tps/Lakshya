@echo off
setlocal enabledelayedexpansion

REM Export only Secure Identity source (no .venv, db, logs, node_modules).
REM Usage:
REM   export_secure_identity_system.bat [DEST_DIR]
REM If DEST_DIR is not provided, exports to: .\secure_identity_system_export

cd /d "%~dp0"

set "SRC_ROOT=%CD%"
set "SRC_SYS=%SRC_ROOT%\secure_identity_system"

if not exist "%SRC_SYS%\backend\app.py" (
  echo ERROR: secure_identity_system not found under "%SRC_ROOT%".
  exit /b 1
)

set "DEST_ROOT=%~1"
if "%DEST_ROOT%"=="" set "DEST_ROOT=%SRC_ROOT%\secure_identity_system_export"

echo === Export Secure Identity System ===
echo Source: "%SRC_SYS%"
echo Dest:   "%DEST_ROOT%"
echo.

mkdir "%DEST_ROOT%" 2>nul

set "ROBO=C:\Windows\System32\Robocopy.exe"

REM Copy backend (exclude runtime folders/caches).
%ROBO% "%SRC_SYS%\backend" "%DEST_ROOT%\secure_identity_system\backend" /E ^
  /XD "__pycache__" "uploads" ^
  /XF "*.pyc" "*.pyo" "*.log" ^
  /NFL /NDL /NJH /NJS >nul

REM Copy templates/static are inside backend; done above.

REM Copy smart contract (exclude node_modules/cache/local artifacts).
%ROBO% "%SRC_SYS%\smart_contract" "%DEST_ROOT%\secure_identity_system\smart_contract" /E ^
  /XD "node_modules" "cache" ".hardhat" ".hardhat-local" ^
  /XF "*.log" ^
  /NFL /NDL /NJH /NJS >nul

REM Ensure ABI artifact file is present if it exists.
if exist "%SRC_SYS%\smart_contract\artifacts\contracts\Identity.sol\IdentityRegistry.json" (
  mkdir "%DEST_ROOT%\secure_identity_system\smart_contract\artifacts\contracts\Identity.sol" 2>nul
  copy /y "%SRC_SYS%\smart_contract\artifacts\contracts\Identity.sol\IdentityRegistry.json" ^
    "%DEST_ROOT%\secure_identity_system\smart_contract\artifacts\contracts\Identity.sol\IdentityRegistry.json" >nul
)

REM Copy top-level scripts/docs (no .env, no db files).
for %%F in (
  "run_secure_identity.bat"
  "start_hardhat.bat"
  "start_secure_identity_stack.bat"
) do (
  if exist "%SRC_ROOT%\%%~F" copy /y "%SRC_ROOT%\%%~F" "%DEST_ROOT%\%%~F" >nul
)

for %%F in (
  "README.md"
  "requirements.txt"
) do (
  if exist "%SRC_SYS%\%%~F" copy /y "%SRC_SYS%\%%~F" "%DEST_ROOT%\secure_identity_system\%%~F" >nul
)

for %%F in (
  "start_server.bat"
  "reset_admin_data.bat"
) do (
  if exist "%SRC_SYS%\%%~F" copy /y "%SRC_SYS%\%%~F" "%DEST_ROOT%\secure_identity_system\%%~F" >nul
)

echo Export complete.
echo Copied to: "%DEST_ROOT%"
exit /b 0

