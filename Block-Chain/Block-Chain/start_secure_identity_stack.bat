@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "HOST=127.0.0.1"
set "CHAIN_PORT=8545"
set "CHAIN_URL=http://%HOST%:%CHAIN_PORT%"
set "POWERSHELL=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"
set "NODE_EXE=node"
set "APP_PORT=5055"
set "APP_URL=http://%HOST%:%APP_PORT%"
if exist "D:\\nodejs\\node.exe" (
  set "PATH=D:\\nodejs;%PATH%"
  set "NODE_EXE=D:\\nodejs\\node.exe"
)

echo.
echo === Secure Identity Stack ===
echo Chain: %CHAIN_URL%
echo App:   %APP_URL%
echo.

rem 1) Ensure the Hardhat RPC is listening.
set "CHAIN_READY="
call :check_port %HOST% %CHAIN_PORT%
if not errorlevel 1 set "CHAIN_READY=1"

if not defined CHAIN_READY (
  echo Starting Hardhat node...
  rem Start the dedicated Hardhat launcher script in a new window.
  start "Hardhat Node" /D "%~dp0" "%~dp0start_hardhat.bat"

  echo Waiting for Hardhat RPC on %HOST%:%CHAIN_PORT% ...
  for /l %%I in (1,1,90) do (
    call :check_port %HOST% %CHAIN_PORT%
    if not errorlevel 1 (
      set "CHAIN_READY=1"
      goto :chain_ready
    )
    if exist "%SystemRoot%\\System32\\timeout.exe" (
      "%SystemRoot%\\System32\\timeout.exe" /t 1 > nul
    )
  )
)

:chain_ready
if not defined CHAIN_READY (
  echo Hardhat RPC did not become ready on %HOST%:%CHAIN_PORT%.
  echo If another app is using the port, stop it and re-run this script.
  exit /b 1
)

rem 2) Deploy contract to localhost and update secure_identity_system\.env
echo Deploying contract (updates secure_identity_system\.env)...
cd /d "%~dp0secure_identity_system\smart_contract"
call npx hardhat run scripts\\deploy.js --network localhost
if errorlevel 1 (
  echo Contract deployment failed. Check the Hardhat Node window and rerun.
  exit /b 1
)

rem 3) Start Flask server + wait until it's listening
echo Starting Flask server...
cd /d "%~dp0"
set "APP_READY="
call :check_port %HOST% %APP_PORT%
if not errorlevel 1 set "APP_READY=1"

if not defined APP_READY (
  set "PORT=%APP_PORT%"
  set "DEBUG=0"
  start "Secure Identity Server" /D "%~dp0secure_identity_system" "%~dp0secure_identity_system\\start_server.bat"
)

if not defined APP_READY (
  echo Waiting for Secure Identity Server on %HOST%:%APP_PORT% ...
  for /l %%I in (1,1,90) do (
    call :check_port %HOST% %APP_PORT%
    if not errorlevel 1 (
      set "APP_READY=1"
      goto :app_ready
    )
    if exist "%SystemRoot%\\System32\\timeout.exe" (
      "%SystemRoot%\\System32\\timeout.exe" /t 1 > nul
    )
  )
)

:app_ready
if not defined APP_READY (
  echo Secure Identity Server did not start on %HOST%:%APP_PORT% within 90 seconds.
  echo Open the "Secure Identity Server" window to see the crash.
  echo Or inspect: %~dp0secure_identity_system\\server-5055.log
  exit /b 1
)

start "" "%APP_URL%/login"

echo.
echo Done. If the dashboard shows "Not Connected", refresh once and check the error text under the badge.
exit /b 0

:check_port
set "CHECK_HOST=%~1"
set "CHECK_PORT=%~2"
if exist "%POWERSHELL%" (
  "%POWERSHELL%" -NoProfile -Command "try { $c = New-Object Net.Sockets.TcpClient; $c.Connect('%CHECK_HOST%', %CHECK_PORT%); $c.Close(); exit 0 } catch { exit 1 }" >nul 2>nul
  exit /b %errorlevel%
)

if not exist "%NODE_EXE%" (
  exit /b 1
)

"%NODE_EXE%" -e "const n=require('net');const h=process.argv[1];const p=Number(process.argv[2]);const s=n.createConnection({host:h,port:p},()=>{s.end();process.exit(0)});s.on('error',()=>process.exit(1));setTimeout(()=>process.exit(1),1000);" "%CHECK_HOST%" "%CHECK_PORT%" >nul 2>nul
exit /b %errorlevel%
