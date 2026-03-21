@echo off
TITLE SENTINEL System Launcher
echo ==============================================
echo SENTINEL SYSTEM INITIALIZATION
echo ==============================================

echo [1/3] Booting Backend (FastAPI + uvicorn on port 8000)...
start "SENTINEL - Backend" cmd /k "cd /d %~dp0backend && python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload"

timeout /t 3 /nobreak >nul

echo [2/3] Booting Traffic Incident Command (Officer Dashboard)...
start "SENTINEL - Officer Dashboard" cmd /k "cd /d %~dp0frontend && npm run dev"

echo [3/3] Booting Citizen Portal (User App)...
start "SENTINEL - Citizen App" cmd /k "cd /d %~dp0user-app && npm run dev"

echo.
echo All services are starting in background windows.
echo - Backend API:         http://localhost:8000
echo - Officer Dashboard:   http://localhost:5173
echo - Citizen Portal:      http://localhost:5174
echo.
pause
