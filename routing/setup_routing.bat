@echo off
:: =============================================================================
:: SENTINEL — Download OSM extracts for local routing
:: =============================================================================
:: Downloads small, city-level OSM extracts from Geofabrik / BBBike.
:: Total size: ~50-250 MB depending on extract boundaries.
::
:: Prerequisites: curl (included in Windows 10+)
:: =============================================================================

TITLE SENTINEL - OSM Data Setup
echo ==============================================
echo  SENTINEL — Local Routing Setup
echo ==============================================
echo.

set "DATA_DIR=%~dp0osm-data"

:: Create data directory
if not exist "%DATA_DIR%" (
    echo [1/4] Creating osm-data directory...
    mkdir "%DATA_DIR%"
) else (
    echo [1/4] osm-data directory exists.
)

:: ── Download Chandigarh region ──────────────────────────────────────────────
:: Using BBBike extract for Chandigarh (tighter boundary = smaller file).
:: Alternatively, full Punjab state from Geofabrik can be used.
set "CHANDIGARH_URL=https://download.geofabrik.de/asia/india/northern-zone-latest.osm.pbf"
set "CHANDIGARH_FILE=%DATA_DIR%\chandigarh.osm.pbf"

echo.
if exist "%CHANDIGARH_FILE%" (
    echo [2/4] Chandigarh OSM extract already downloaded.
) else (
    echo [2/4] Downloading Chandigarh region OSM data...
    echo       Source: %CHANDIGARH_URL%
    echo       This may take a few minutes depending on your connection...
    curl -L -o "%CHANDIGARH_FILE%" "%CHANDIGARH_URL%"
    if %errorlevel% neq 0 (
        echo       ERROR: Download failed. Trying alternate source...
        set "CHANDIGARH_URL_ALT=https://download.geofabrik.de/asia/india-latest.osm.pbf"
        echo       Alternate: %CHANDIGARH_URL_ALT%
        echo       WARNING: Full India extract is large (~1 GB). Consider using osmium to clip.
        curl -L -o "%CHANDIGARH_FILE%" "%CHANDIGARH_URL_ALT%"
    )
    echo       Done.
)

:: ── Download NYC region ─────────────────────────────────────────────────────
set "NYC_URL=https://download.geofabrik.de/north-america/us/new-york-latest.osm.pbf"
set "NYC_FILE=%DATA_DIR%\nyc.osm.pbf"

echo.
if exist "%NYC_FILE%" (
    echo [3/4] NYC OSM extract already downloaded.
) else (
    echo [3/4] Downloading New York State OSM data...
    echo       Source: %NYC_URL%
    echo       This may take a few minutes depending on your connection...
    curl -L -o "%NYC_FILE%" "%NYC_URL%"
    if %errorlevel% neq 0 (
        echo       ERROR: Download failed. Please download manually from:
        echo       %NYC_URL%
        echo       Save to: %NYC_FILE%
    )
    echo       Done.
)

:: ── Start Docker containers ─────────────────────────────────────────────────
echo.
echo [4/4] Starting local ORS routing containers...
echo       First startup will build routing graphs (2-10 min per city).
echo       Subsequent starts are instant.
echo.

:: Check if Docker is available
where docker >nul 2>nul
if %errorlevel% neq 0 (
    echo ERROR: Docker not found in PATH.
    echo Please install Docker Desktop from https://www.docker.com/products/docker-desktop
    echo Then re-run this script.
    pause
    exit /b 1
)

docker compose -f "%~dp0docker-compose.yml" up -d

echo.
echo ==============================================
echo  Setup complete!
echo ==============================================
echo.
echo  Chandigarh ORS: http://localhost:8081/ors/v2/health
echo  NYC ORS:        http://localhost:8082/ors/v2/health
echo.
echo  Wait 2-10 minutes for graph building on first launch.
echo  Check health endpoints to confirm readiness.
echo.
echo  To stop:  docker compose -f routing/docker-compose.yml down
echo  To restart: docker compose -f routing/docker-compose.yml restart
echo.
pause
