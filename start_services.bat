@echo off
REM Nexus Assistant - Start Python Services
REM Simple script to start just the Python backend services

setlocal enabledelayedexpansion

echo ========================================
echo    Nexus Assistant - Services Startup
echo ========================================
echo.

REM Check Python
echo [1/4] Checking Python...
where python >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Python not found
    echo Please install Python 3.11+ from https://www.python.org/
    pause
    exit /b 1
)
echo [OK] Python found
python --version
echo.

REM Create/activate virtual environment
echo [2/4] Setting up virtual environment...
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)
call venv\Scripts\activate.bat
echo [OK] Virtual environment activated
echo.

REM Install dependencies
echo [3/4] Installing Python dependencies...
if not exist "venv\Lib\site-packages\fastapi" (
    echo Installing dependencies (this may take a few minutes)...
    pip install --quiet --upgrade pip
    pip install -r requirements.txt
    echo [OK] Dependencies installed
) else (
    echo [OK] Dependencies already installed
)
echo.

REM Create directories
if not exist "data" mkdir data
if not exist "logs" mkdir logs
if not exist "chroma_data" mkdir chroma_data

REM Check .env
if not exist ".env" (
    echo [WARNING] .env file not found
    if exist ".env.example" (
        echo Creating .env from template...
        copy .env.example .env >nul
        echo.
        echo [IMPORTANT] Please edit .env and add your API keys
        echo Press any key to open .env for editing...
        pause >nul
        notepad .env
        echo.
    )
)

echo [4/4] Starting services...
echo.
echo ========================================
echo Services starting on:
echo   - Transcription: http://127.0.0.1:38421
echo   - LLM:           http://127.0.0.1:45231
echo   - RAG:           http://127.0.0.1:53847
echo ========================================
echo.
echo Press Ctrl+C to stop all services
echo.
echo.

REM Start services
cd src\python

REM Start Transcription Service in new window
start "Transcription Service" cmd /k "..\..\venv\Scripts\activate.bat && python -m uvicorn transcription_service:app --host 127.0.0.1 --port 38421"

REM Wait a bit before starting next service
timeout /t 2 /nobreak >nul

REM Start LLM Service in new window
start "LLM Service" cmd /k "..\..\venv\Scripts\activate.bat && python -m uvicorn llm_service:app --host 127.0.0.1 --port 45231"

REM Wait a bit before starting next service
timeout /t 2 /nobreak >nul

REM Start RAG Service in new window
start "RAG Service" cmd /k "..\..\venv\Scripts\activate.bat && python -m uvicorn rag_service:app --host 127.0.0.1 --port 53847"

cd ..\..

echo.
echo ========================================
echo [SUCCESS] All services started!
echo ========================================
echo.
echo Services are running in separate windows.
echo Check each window for service status.
echo.
echo Test services with:
echo   curl http://127.0.0.1:38421/health
echo   curl http://127.0.0.1:45231/health
echo   curl http://127.0.0.1:53847/health
echo.
echo Close this window to keep services running,
echo or close each service window to stop them.
echo.
pause
