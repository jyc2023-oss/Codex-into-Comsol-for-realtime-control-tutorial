@echo off
setlocal

set "COMSOL_SERVER=D:\COMSOL\bin\win64\comsolmphserver.exe"
set "COMSOL_PORT=2036"
set "COMSOL_LOGIN=auto"
set "COMSOL_TMPDIR=F:\simulation\comsol_tmp"
set "COMSOL_JAVA_HEAP=16g"

if not exist "%COMSOL_SERVER%" (
  echo [ERROR] Could not find COMSOL server executable:
  echo         %COMSOL_SERVER%
  exit /b 1
)

if not exist "%COMSOL_TMPDIR%" (
  mkdir "%COMSOL_TMPDIR%"
)

echo [INFO] Starting COMSOL server on port %COMSOL_PORT% in multi-client mode...
echo [INFO] Login mode: %COMSOL_LOGIN%
echo [INFO] Temp dir: %COMSOL_TMPDIR%
echo [INFO] Java heap: %COMSOL_JAVA_HEAP%
"%COMSOL_SERVER%" -multi on -login %COMSOL_LOGIN% -port %COMSOL_PORT% -tmpdir "%COMSOL_TMPDIR%" -J-Xmx%COMSOL_JAVA_HEAP%
