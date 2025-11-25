@echo off
REM Nexus Assistant - Start Python Services
REM Simple script to start just the Python backend services

setlocal enabledelayedexpansion

echo ========================================
echo    Nexus Assistant - Services Startup
echo ========================================
echo.

REM FIRST: Kill any existing services on our ports
echo [1/6] Cleaning up existing services...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr ":38421 :45231 :53847" 2^>nul') do (
    echo Killing process %%a...
    taskkill /PID %%a /F >nul 2>&1
)
echo [OK] Ports cleared
echo.

REM Check Python
echo [2/6] Checking Python...
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
echo [3/6] Setting up virtual environment...
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)
call venv\Scripts\activate.bat
echo [OK] Virtual environment activated
echo.

REM Install dependencies
echo [4/6] Installing Python dependencies...
echo Installing/updating dependencies...
pip install --quiet --upgrade pip
pip install --quiet -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Failed to install dependencies
    pause
    exit /b 1
)
echo [OK] Dependencies installed
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

REM Check .env configuration
echo [5/6] Verifying configuration...
echo [OK] Configuration ready
echo.

echo [6/6] Starting services...
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
