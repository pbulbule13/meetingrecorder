@echo off
REM Nexus Assistant - Automated Setup Script for Windows
REM This script installs all dependencies and prepares the environment

echo =========================================
echo    Nexus Assistant - Setup Script
echo =========================================
echo.

REM Step 1: Check prerequisites
echo Step 1: Checking prerequisites...
echo -----------------------------------

REM Check Node.js
where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Node.js is not installed
    echo Please install Node.js 20+ from https://nodejs.org/
    exit /b 1
) else (
    echo [OK] Node.js is installed
    node -v
)

REM Check Python
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python is not installed
    echo Please install Python 3.11+ from https://www.python.org/
    exit /b 1
) else (
    echo [OK] Python is installed
    python --version
)

REM Check FFmpeg
where ffmpeg >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] FFmpeg is not installed
    echo Please install FFmpeg from https://ffmpeg.org/ or use:
    echo   choco install ffmpeg
    echo.
    echo Continuing without FFmpeg (you'll need to install it later)
) else (
    echo [OK] FFmpeg is installed
    ffmpeg -version | findstr /C:"ffmpeg version"
)

echo.

REM Step 2: Install Node.js dependencies
echo Step 2: Installing Node.js dependencies...
echo -------------------------------------------

call npm install

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install Node.js dependencies
    exit /b 1
)

echo [OK] Node.js dependencies installed
echo.

REM Step 3: Install Python dependencies
echo Step 3: Installing Python dependencies...
echo -----------------------------------------

REM Create virtual environment
if not exist "venv" (
    echo [INFO] Creating Python virtual environment...
    python -m venv venv
)

REM Activate virtual environment
echo [INFO] Activating virtual environment...
call venv\Scripts\activate.bat

REM Upgrade pip
echo [INFO] Upgrading pip...
python -m pip install --upgrade pip

REM Install dependencies
echo [INFO] Installing Python packages...
pip install -r requirements.txt

if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install Python dependencies
    exit /b 1
)

echo [OK] Python dependencies installed
echo.

REM Step 4: Setup environment file
echo Step 4: Configuring environment...
echo -----------------------------------

if not exist ".env" (
    echo [INFO] Creating .env file from template...
    copy .env.example .env
    echo [OK] .env file created
    echo.
    echo [IMPORTANT] Edit .env file and add your API keys:
    echo    - DEEPGRAM_API_KEY or ASSEMBLYAI_API_KEY or OPENAI_API_KEY (for STT)
    echo    - GEMINI_API_KEY or OPENAI_API_KEY or ANTHROPIC_API_KEY (for LLM)
    echo.
) else (
    echo [INFO] .env file already exists (not overwriting)
)

echo.

REM Step 5: Create necessary directories
echo Step 5: Creating data directories...
echo -------------------------------------

if not exist "data\meetings" mkdir data\meetings
if not exist "data\transcripts" mkdir data\transcripts
if not exist "data\audio" mkdir data\audio
if not exist "logs" mkdir logs

echo [OK] Data directories created
echo.

REM Step 6: Run tests (optional)
echo Step 6: Running tests (optional)...
echo ------------------------------------

set /p RUNTESTS="Do you want to run tests now? (y/N): "

if /i "%RUNTESTS%"=="y" (
    echo [INFO] Running tests...
    call npm test
    echo [OK] Tests completed
) else (
    echo [INFO] Skipping tests
)

echo.

REM Setup complete
echo =========================================
echo    Setup Complete! 🎉
echo =========================================
echo.
echo Next steps:
echo 1. Edit .env file and add your API keys
echo 2. Run 'npm run dev' to start the application
echo 3. Check DOCUMENTATION.html for full documentation
echo.
echo Useful commands:
echo   npm run dev          - Start in development mode
echo   npm test             - Run tests
echo   npm run build:win    - Build Windows installer
echo.
echo [OK] Happy meeting recording!
echo.

pause
