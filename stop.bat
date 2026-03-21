@echo off
cd /d %~dp0

echo ============================================
echo        SENTINEL - Stopping Services
echo ============================================
echo.

echo [1/2] Looking for uvicorn processes...
tasklist /fi "imagename eq python.exe" 2>nul | findstr /i "python" >nul
if %errorlevel% equ 0 (
    echo       Found Python processes. Killing uvicorn...
    taskkill /f /fi "windowtitle eq SENTINEL Backend*" >nul 2>nul
    taskkill /f /im uvicorn.exe >nul 2>nul
    :: Also kill python processes that were running uvicorn
    for /f "tokens=2" %%a in ('wmic process where "commandline like '%%uvicorn%%'" get processid 2^>nul ^| findstr /r "[0-9]"') do (
        taskkill /f /pid %%a >nul 2>nul
    )
    echo       Uvicorn processes terminated.
) else (
    echo       No Python processes found.
)

echo.
echo [2/2] Closing SENTINEL Backend window...
taskkill /f /fi "windowtitle eq SENTINEL Backend" >nul 2>nul

echo.
echo ============================================
echo   SENTINEL services stopped.
echo ============================================
echo.
pause
