@echo off
setlocal
cd /d "%~dp0"
set PYTHONUTF8=1
if not exist ".venv\Scripts\python.exe" (
  echo Run SETUP-WINDOWS.bat in the parent folder before using this launcher.
  exit /b 1
)
".venv\Scripts\python.exe" brandforge.py %*
set "RESULT=%ERRORLEVEL%"
if not "%RESULT%"=="0" echo BrandForge did not complete successfully. Check the message above.
exit /b %RESULT%
