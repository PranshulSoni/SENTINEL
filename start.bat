@echo off
cd /d %~dp0

echo ============================================
echo        SENTINEL - Smart Transport System
echo ============================================
echo.

:: -------------------------------------------
:: Backend Setup
:: -------------------------------------------
echo [1/5] Checking Python virtual environment...
if not exist "backend\venv" (
    echo       Virtual environment not found. Creating...
    python -m venv backend\venv
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to create virtual environment. Is Python installed?
        pause
        exit /b 1
    )
    echo       Virtual environment created successfully.
) else (
    echo       Virtual environment already exists.
)

echo.
echo [2/5] Activating virtual environment and installing backend dependencies...
call backend\venv\Scripts\activate.bat
pip install -r backend\requirements.txt --quiet
if %errorlevel% neq 0 (
    echo [ERROR] Failed to install backend dependencies.
    pause
    exit /b 1
)
echo       Backend dependencies installed.

echo.
echo [3/5] Starting SENTINEL Backend (uvicorn) in a new window...
start "SENTINEL Backend" cmd /k "cd /d %~dp0 && call backend\venv\Scripts\activate.bat && cd backend && python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload"
echo       Backend server launching at http://127.0.0.1:8000

:: -------------------------------------------
:: Frontend Setup
:: -------------------------------------------
echo.
echo [4/5] Checking for npm...
where npm >nul 2>nul
if %errorlevel% neq 0 (
    echo [ERROR] npm is not installed or not in PATH.
    echo         Please install Node.js from https://nodejs.org
    echo         Backend is still running in the other window.
    pause
    exit /b 1
)

echo [5/5] Installing frontend dependencies and starting dev server...
cd frontend
call npm install --silent
if %errorlevel% neq 0 (
    echo [ERROR] npm install failed.
    pause
    exit /b 1
)

echo.
echo ============================================
echo   SENTINEL is starting up!
echo   Backend:  http://127.0.0.1:8000
echo   Frontend: Starting below...
echo   Use stop.bat to shut down the backend.
echo ============================================
echo.

npm run dev
