@echo off
echo ===================================================
echo   TarFixer Local Backend Launcher
echo ===================================================

REM Check for Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in your PATH.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    pause
    exit /b
)

REM Navigate to backend directory
cd /d "%~dp0"

REM Check if venv exists, create if not
if not exist ".venv" (
    echo [INFO] Creating virtual environment...
    python -m venv .venv
)

REM Activate venv
call .venv\Scripts\activate

REM Install dependencies
echo [INFO] Installing/Updating dependencies...
pip install -r requirements.txt

REM Run server
echo.
echo [INFO] Starting Flask Server...
echo [INFO] API will be available at: http://localhost:5000
echo.
python backend\server.py

pause
