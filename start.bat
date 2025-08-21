@echo off
REM RemindMine AI Agent startup script for Windows

cd /d "%~dp0"

echo Starting RemindMine AI Agent...
echo.

REM Check if .env file exists
if not exist ".env" (
    echo Error: .env file not found!
    echo Please copy .env.example to .env and configure your settings.
    pause
    exit /b 1
)

REM Check if virtual environment exists
if not exist ".venv\Scripts\python.exe" (
    echo Error: Virtual environment not found!
    echo Please run: python -m venv .venv
    echo Then: .venv\Scripts\activate
    echo Then: pip install -e .
    pause
    exit /b 1
)

REM Activate virtual environment and start the server
echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo Starting FastAPI server...
python cli.py server

pause
