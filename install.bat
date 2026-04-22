@echo off
rem WebFace - Installation Script for Windows
rem This script sets up the application environment

setlocal enabledelayedexpansion

echo ========================================
echo    WebFace Installation Script
echo ========================================
echo.

rem Check if Python is installed
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed
    pause
    exit /b 1
)

echo [OK] Python found
python --version
echo.

rem Check if virtual environment exists
if exist "venv" (
    echo [WARNING] Virtual environment 'venv' already exists
    set /p use_existing="Use existing venv? (y/n): "
    if /i not "!use_existing!"=="y" (
        echo Aborted.
        pause
        exit /b 1
    )
) else (
    echo [INFO] Creating virtual environment...
    python -m venv venv
)

rem Activate virtual environment
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

rem Upgrade pip
echo [INFO] Upgrading pip...
pip install --upgrade pip

rem Install dependencies
echo [INFO] Installing dependencies...
pip install -r requirements.txt

rem Copy .env.example if .env doesn't exist
if not exist ".env" (
    echo.
    echo [INFO] Creating .env file from .env.example...
    copy .env.example .env
    echo [OK] Created .env file
    echo.
    echo [WARNING] Please edit .env file with your configuration:
    echo   - SECRET_KEY
    echo   - COMFY_URL (ComfyUI API endpoint)
    echo   - DATABASE_URL (PostgreSQL for production)
    echo.
    set /p configure_env="Do you want to configure these now? (y/n): "
    if /i "!configure_env!"=="y" (
        echo.
        
        rem Generate SECRET_KEY
        for /f "delims=" %%i in ('python -c "import secrets; print(secrets.token_hex(32))"') do set SECRET_KEY=%%i
        echo [OK] Generated SECRET_KEY
        
        rem Update .env
        powershell -Command "(Get-Content .env) -replace 'SECRET_KEY=.*', 'SECRET_KEY=%SECRET_KEY%' | Set-Content .env"
        
        echo.
        set /p comfy_url="Enter COMFY_URL (default: http://127.0.0.1:8188): "
        if "%comfy_url%"=="" set comfy_url=http://127.0.0.1:8188
        powershell -Command "(Get-Content .env) -replace 'COMFY_URL=.*', 'COMFY_URL=%comfy_url%' | Set-Content .env"
        
        echo.
        echo [OK] Updated .env file
    )
)

rem Initialize database
echo.
echo [INFO] Initializing database...
python -c "from app import app, db; from models import *; app.app_context().push(); db.create_all(); print('Database initialized successfully')"

rem Run migration if database exists
if exist "webface.db" (
    echo [WARNING] Database file found. Running migration...
    python migrate_db.py --backup
)

rem Create admin user
echo.
echo [INFO] Creating administrator account...
python create_admin.py

echo.
echo ========================================
echo    Installation Complete!
echo ========================================
echo.
echo [INFO] Next steps:
echo 1. Start the application: python app.py
echo 2. Access the web interface at http://localhost:5000
echo 3. Log in with your admin credentials
echo.
echo [WARNING] Important:
echo - Edit .env file to configure Telegram bot
echo - For production, set FLASK_ENV=production and use HTTPS
echo.

pause
