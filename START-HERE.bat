@echo off
setlocal
title BrandForge OS - Local launch
cd /d "%~dp0app"
if not exist ".venv\Scripts\python.exe" (
  echo Setup is required. Close this window and run SETUP-WINDOWS.bat while online.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" setup_env.py --check
if errorlevel 1 (
  echo The setup fingerprint changed. Run SETUP-WINDOWS.bat to update or repair.
  pause
  exit /b 1
)
echo Opening BrandForge OS at http://127.0.0.1:8000
".venv\Scripts\python.exe" brandforge.py --server --open-browser
if errorlevel 1 pause
endlocal
