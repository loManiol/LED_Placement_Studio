@echo off
cd /d "%~dp0"

echo ============================================
echo   LED Placement Studio
echo ============================================
echo.

REM If a local venv exists, use it; otherwise use system Python
if exist "venv\Scripts\python.exe" goto use_venv
goto use_system

:use_venv
echo Using local virtual environment...
call "venv\Scripts\activate.bat"
goto run_app

:use_system
echo Using system Python...
goto run_app

:run_app
echo.
echo Starting app...
echo.
python main.py
if errorlevel 1 goto fail
goto end

:fail
echo.
echo Application exited with an error.
pause
goto end

:end
