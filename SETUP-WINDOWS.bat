@echo off
setlocal
title BrandForge OS - Explicit setup or repair
cd /d "%~dp0"
echo This setup downloads Python dependencies. An internet connection is required.
echo Existing campaign data is not removed.
set "PY="
py -3 --version >nul 2>nul && set "PY=py -3"
if not defined PY (
  python --version >nul 2>nul
  if not errorlevel 1 set "PY=python"
)
if not defined PY (
  echo Install Python 3.10 or newer from python.org with Add Python to PATH enabled.
  pause
  exit /b 1
)
%PY% app\setup_env.py --install
if errorlevel 1 (
  echo Setup did not complete. Check the error above before retrying.
  pause
  exit /b 1
)
echo Setup complete. Run START-HERE.bat to launch, including when offline.
pause
endlocal
