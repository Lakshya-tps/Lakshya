@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "HOST=127.0.0.1"
set "PORT=5055"
set "DEBUG=0"

if not exist "%~dp0secure_identity_system\start_server.bat" (
  echo Flask launcher not found: "%~dp0secure_identity_system\start_server.bat"
  exit /b 1
)

set HOST=%HOST%
set PORT=%PORT%
set DEBUG=%DEBUG%

call "%~dp0secure_identity_system\start_server.bat"
