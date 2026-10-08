@echo off
setlocal
cd /d "%~dp0"

set "PYTHON_CMD="
where py >nul 2>nul && set "PYTHON_CMD=py"
if not defined PYTHON_CMD (
  where python >nul 2>nul && set "PYTHON_CMD=python"
)
if not defined PYTHON_CMD (
  echo No se encontro Python. Instale Python 3.11 o superior desde python.org.
  echo Durante la instalacion marque la opcion Add Python to PATH.
  pause
  exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
  %PYTHON_CMD% -m venv .venv
)

".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt

if errorlevel 1 (
  echo Ocurrio un error durante la instalacion.
  pause
  exit /b 1
)

echo.
echo Instalacion terminada correctamente.
echo Ejecute run.bat para abrir la aplicacion.
pause
