@echo off
setlocal
cd /d "%~dp0"
if not exist "frontend\public\squad\embed.html" (
  echo ERROR: Faltan los archivos de UI-2. Aplica el parche en la raiz del juego.
  pause
  exit /b 1
)
set "PYTHONPATH=%~dp0src"
echo.
echo FM PROJECT - Interfaz portable con Python
echo Node.js y npm NO son necesarios.
echo Iniciando... (puede tardar unos segundos)
echo Cierra esta ventana o usa Ctrl+C para detener el servidor.
echo.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" -m football_manager.ui_shell
) else (
  where python >nul 2>&1
  if not errorlevel 1 (
    python -m football_manager.ui_shell
  ) else (
    py -3 -m football_manager.ui_shell
  )
)
if errorlevel 1 (
  echo.
  echo ERROR: No se pudo iniciar la interfaz.
  echo Comproba que Python funcione y que este completo el repositorio.
  pause
  exit /b 1
)
endlocal
