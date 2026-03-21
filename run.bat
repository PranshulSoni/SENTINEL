@echo off
TITLE SENTINEL System Launcher
echo ==============================================
echo SENTINEL SYSTEM INITIALIZATION
echo ==============================================

echo [1/2] Booting Traffic Incident Command (Officer Dashboard)...
start "SENTINEL - Officer Dashboard" cmd /k "cd frontend && npm run dev"

echo [2/2] Booting Citizen Portal (User App)...
start "SENTINEL - Citizen App" cmd /k "cd user-app && npm run dev"

echo.
echo Both applications are starting in background windows.
echo - Officer Dashboard will be available at: http://localhost:5173
echo - Citizen Portal will be available at: http://localhost:3000
echo.
pause
