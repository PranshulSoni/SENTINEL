@echo off
cd /d %~dp0

echo ============================================
echo        SENTINEL - Smart Transport System
echo ============================================
echo.

:: Start local ORS routing containers (if Docker is available)
where docker >nul 2>nul
if %errorlevel% equ 0 (
    if exist "%~dp0routing\docker-compose.yml" (
        echo Starting local ORS routing containers...
        docker compose -f "%~dp0routing\docker-compose.yml" up -d >nul 2>nul
        if %errorlevel% neq 0 (
            docker-compose -f "%~dp0routing\docker-compose.yml" up -d >nul 2>nul
        )
        if %errorlevel% equ 0 (
            echo   Local routing started (Chandigarh :8081, NYC :8082^)
        ) else (
            echo   Local routing not available - using remote ORS API
        )
    )
) else (
    echo   Docker not found - using remote ORS API for routing
)
echo.

echo Starting SENTINEL Backend (uvicorn)...
start "SENTINEL Backend" cmd /k "cd /d %~dp0backend && set CUDA_VISIBLE_DEVICES=0 && if exist ..\venv\Scripts\python.exe (..\venv\Scripts\python.exe -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload) else (python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload)"

timeout /t 3 /nobreak >nul

echo Starting SENTINEL User App in a new window...
start "SENTINEL User App" cmd /k "cd /d %~dp0user-app && npm run dev"

echo Starting SENTINEL Admin / Main Frontend in a new window...
start "SENTINEL Frontend" cmd /k "cd /d %~dp0frontend && npm run dev"
