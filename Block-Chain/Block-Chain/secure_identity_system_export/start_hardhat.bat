@echo off
setlocal
cd /d %~dp0
set "PATH=D:\nodejs;%PATH%"
set "APPDATA=%~dp0.hardhat"
set "LOCALAPPDATA=%~dp0.hardhat-local"
set "HARDHAT_DISABLE_TELEMETRY=1"

if not exist "%APPDATA%" mkdir "%APPDATA%"
if not exist "%LOCALAPPDATA%" mkdir "%LOCALAPPDATA%"

if not exist secure_identity_system\smart_contract (
  echo smart_contract directory not found.
  exit /b 1
)

cd /d %~dp0secure_identity_system\smart_contract
if not exist "node_modules" (
  echo node_modules not found in smart_contract. Install dependencies first.
  exit /b 1
)

set "HARDHAT_LOG=%~dp0hardhat-node.log"
set "POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"

echo Hardhat RPC: http://127.0.0.1:8545
echo Log file: %HARDHAT_LOG%
echo.

if exist "%POWERSHELL%" (
  "%POWERSHELL%" -NoProfile -Command "npx hardhat node 2>&1 | Tee-Object -FilePath '%HARDHAT_LOG%'" 
) else (
  call npx hardhat node
)
