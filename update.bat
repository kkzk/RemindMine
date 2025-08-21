@echo off
REM Update RAG database script for Windows

cd /d "%~dp0"

echo Updating RemindMine RAG Database...
echo.

REM Check if .env file exists
if not exist ".env" (
    echo Error: .env file not found!
    echo Please copy .env.example to .env and configure your settings.
    pause
    exit /b 1
)

REM Activate virtual environment and run update
echo Activating virtual environment...
call .venv\Scripts\activate.bat

echo Fetching issues from Redmine and updating ChromaDB...
python cli.py update

echo.
echo RAG database update completed!
pause
