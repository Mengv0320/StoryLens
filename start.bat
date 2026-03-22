@echo off
setlocal

set SCRIPT_DIR=%~dp0

:: Check Python
where python >nul 2>&1
if errorlevel 1 (
    echo ERROR: python not found. Please install Python 3.9+.
    exit /b 1
)

:: Build frontend if dist doesn't exist
if not exist "%SCRIPT_DIR%gui\dist" (
    echo [start.bat] gui\dist not found, building frontend...
    where npm >nul 2>&1
    if errorlevel 1 (
        echo ERROR: npm not found. Please install Node.js.
        exit /b 1
    )
    cd /d "%SCRIPT_DIR%gui"
    call npm run build
    if errorlevel 1 (
        echo ERROR: Frontend build failed.
        exit /b 1
    )
    cd /d "%SCRIPT_DIR%"
)

echo [start.bat] Starting server...
echo [start.bat] Access: http://localhost:8765
cd /d "%SCRIPT_DIR%"
python -m src.api_server
