@echo off
echo 🎨 ComfyUI Web Interface Setup
echo ================================
echo.

:: Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python не найден. Установите Python 3.8+
    pause
    exit /b 1
)

echo ✓ Python найден
python --version

:: Create virtual environment
echo.
echo 📦 Создание виртуального окружения...
python -m venv venv

:: Activate virtual environment
call venv\Scripts\activate.bat

:: Upgrade pip
echo.
echo 📥 Обновление pip...
python -m pip install --upgrade pip

:: Install dependencies
echo.
echo 📥 Установка зависимостей...
pip install -r requirements.txt

:: Create .env if not exists
if not exist .env (
    echo.
    echo ⚙️  Создание .env файла...
    copy .env.example .env
    echo ✏️  Отредактируйте .env файл с вашими настройками!
)

:: Create folders
echo.
echo 📁 Создание папок...
mkdir uploads 2>nul
mkdir results 2>nul
mkdir instance 2>nul
mkdir workflows\text_to_image 2>nul
mkdir workflows\text_to_video 2>nul
mkdir workflows\image_edit 2>nul

:: Create .gitkeep files
type nul > uploads\.gitkeep
type nul > results\.gitkeep

:: Initialize database
echo.
echo 🗄️  Инициализация базы данных...
python -c "from app import app, db; app.app_context().push(); db.create_all(); print('Database created successfully!')"

echo.
echo ================================
echo ✅ Установка завершена!
echo.
echo Следующие шаги:
echo 1. Отредактируйте .env файл
echo.
echo 2. Убедитесь что ComfyUI запущен:
echo    cd C:\path\to\ComfyUI
echo    python main.py --listen
echo.
echo 3. Запустите веб-интерфейс:
echo    venv\Scripts\activate
echo    python app.py
echo.
echo 4. Откройте в браузере:
echo    http://localhost:5000
echo.
echo ================================
pause