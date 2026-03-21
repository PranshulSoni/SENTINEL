@echo off
cd /d %~dp0

echo ============================================
echo        SENTINEL - Smart Transport System
echo ============================================
echo.

echo Starting SENTINEL Backend (uvicorn)...
start "SENTINEL Backend" cmd /k "cd /d %~dp0backend && python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload"

timeout /t 3 /nobreak >nul

echo Starting SENTINEL User App in a new window...
start "SENTINEL User App" cmd /k "cd /d %~dp0user-app && npm run dev"

echo Starting SENTINEL Admin / Main Frontend...
cd frontend
npm run dev
