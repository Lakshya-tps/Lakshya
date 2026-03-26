@echo off
setlocal
set "PATH=D:\nodejs;%PATH%"
set "APPDATA=%~dp0.hardhat"
set "LOCALAPPDATA=%~dp0.hardhat-local"
set "HARDHAT_DISABLE_TELEMETRY=1"

if not exist "%APPDATA%" mkdir "%APPDATA%"
if not exist "%LOCALAPPDATA%" mkdir "%LOCALAPPDATA%"

cd /d "%~dp0secure_identity_system\smart_contract"
if not exist "node_modules" (
  echo node_modules not found in smart_contract. Install dependencies first.
  exit /b 1
)

call npx hardhat run scripts\deploy.js --network localhost
