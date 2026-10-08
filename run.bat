@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo La aplicacion todavia no esta instalada.
  echo Ejecute primero install.bat.
  pause
  exit /b 1
)

".venv\Scripts\python.exe" start.py

if errorlevel 1 (
  echo.
  echo La aplicacion se cerro con un error.
  pause
)
