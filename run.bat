@echo off
REM Nexus Assistant - Automated Run Script
REM Uses UV package manager for fast Python dependency installation
REM This script handles all setup and launches the application

setlocal enabledelayedexpansion

echo ========================================
echo    Nexus Assistant - Quick Start
echo ========================================
echo.

REM Colors (Windows 10+ ANSI support)
set "GREEN=[92m"
set "YELLOW=[93m"
set "RED=[91m"
set "NC=[0m"

REM Step 1: Check Node.js
echo [1/7] Checking Node.js...
where node >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo %RED%[ERROR]%NC% Node.js not found
    echo Please install Node.js 20+ from https://nodejs.org/
    pause
    exit /b 1
)
echo %GREEN%[OK]%NC% Node.js found
node -v

REM Step 2: Check Python
echo.
echo [2/7] Checking Python...
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo %RED%[ERROR]%NC% Python not found
    echo Please install Python 3.11+ from https://www.python.org/
    pause
    exit /b 1
)
echo %GREEN%[OK]%NC% Python found
python --version

REM Step 3: Install/Check UV package manager
echo.
echo [3/7] Setting up UV package manager...
where uv >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo %YELLOW%[INFO]%NC% UV not found, installing...
    pip install uv
    if %ERRORLEVEL% NEQ 0 (
        echo %RED%[ERROR]%NC% Failed to install UV
        echo Falling back to pip...
        set USE_PIP=1
    ) else (
        echo %GREEN%[OK]%NC% UV installed
    )
) else (
    echo %GREEN%[OK]%NC% UV already installed
)

REM Step 4: Check FFmpeg
echo.
echo [4/7] Checking FFmpeg...
where ffmpeg >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo %YELLOW%[WARNING]%NC% FFmpeg not found
    echo Audio capture will not work without FFmpeg
    echo Install with: choco install ffmpeg
    echo.
    echo Continue anyway? (Y/N)
    set /p CONTINUE=
    if /i not "!CONTINUE!"=="Y" exit /b 1
) else (
    echo %GREEN%[OK]%NC% FFmpeg found
)

REM Step 5: Install Node.js dependencies
echo.
echo [5/7] Installing Node.js dependencies...
if not exist "node_modules" (
    echo %YELLOW%[INFO]%NC% Running npm install...
    call npm install --silent
    if %ERRORLEVEL% NEQ 0 (
        echo %RED%[ERROR]%NC% Failed to install Node.js dependencies
        pause
        exit /b 1
    )
    echo %GREEN%[OK]%NC% Node.js dependencies installed
) else (
    echo %GREEN%[OK]%NC% Node.js dependencies already installed
)

REM Step 6: Install Python dependencies with UV
echo.
echo [6/7] Installing Python dependencies...

REM Create virtual environment if doesn't exist
if not exist "venv" (
    echo %YELLOW%[INFO]%NC% Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install with UV or fall back to pip
if defined USE_PIP (
    echo %YELLOW%[INFO]%NC% Using pip to install dependencies...
    pip install --upgrade pip
    pip install -r requirements.txt
) else (
    echo %YELLOW%[INFO]%NC% Using UV to install dependencies (faster)...
    uv pip install -r requirements.txt
)

if %ERRORLEVEL% NEQ 0 (
    echo %RED%[ERROR]%NC% Failed to install Python dependencies
    pause
    exit /b 1
)
echo %GREEN%[OK]%NC% Python dependencies installed

REM Step 7: Check .env file
echo.
echo [7/7] Checking configuration...
if not exist ".env" (
    echo %YELLOW%[WARNING]%NC% .env file not found
    if exist ".env.example" (
        echo %YELLOW%[INFO]%NC% Creating .env from .env.example...
        copy .env.example .env
        echo.
        echo %YELLOW%[IMPORTANT]%NC% Please edit .env and add your API keys:
        echo   - At least one STT provider key (DEEPGRAM/ASSEMBLYAI/OPENAI)
        echo   - At least one LLM provider key (GEMINI/OPENAI/ANTHROPIC)
        echo.
        echo Edit .env now? (Y/N)
        set /p EDITENV=
        if /i "!EDITENV!"=="Y" notepad .env
    )
) else (
    echo %GREEN%[OK]%NC% Configuration found
)

REM Create data directories
if not exist "data" mkdir data
if not exist "data\meetings" mkdir data\meetings
if not exist "data\transcripts" mkdir data\transcripts
if not exist "data\audio" mkdir data\audio
if not exist "logs" mkdir logs

echo.
echo ========================================
echo    Starting Nexus Assistant...
echo ========================================
echo.
echo Services will start on:
echo   - Transcription: http://localhost:38421
echo   - LLM:           http://localhost:45231
echo   - RAG:           http://localhost:53847
echo   - API Server:    http://localhost:62194
echo.
echo Press Ctrl+C to stop all services
echo.

REM Start the application
npm run dev

REM Cleanup on exit
:cleanup
echo.
echo ========================================
echo    Shutting down...
echo ========================================
deactivate
exit /b 0
