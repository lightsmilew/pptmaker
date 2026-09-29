@echo off
REM PPTMaker Build Script for Windows
REM Usage: scripts\build.bat

echo === PPTMaker Build Script ===
echo.

setlocal enabledelayedexpansion

set "PROJECT_ROOT=%~dp0.."
set "BACKEND_DIR=%PROJECT_ROOT%\backend"
set "FRONTEND_DIR=%PROJECT_ROOT%\frontend"
set "DIST_DIR=%PROJECT_ROOT%\dist"

echo [1/4] Cleaning dist directory...
if exist "%DIST_DIR%" rmdir /s /q "%DIST_DIR%"
mkdir "%DIST_DIR%"

echo [2/4] Building frontend...
cd /d "%FRONTEND_DIR%"
call npm run build
if errorlevel 1 (
    echo Frontend build failed!
    exit /b 1
)

echo [3/4] Copying backend files...
xcopy /s /e /y "%BACKEND_DIR%\app" "%DIST_DIR%\app\"
copy "%BACKEND_DIR%\pyproject.toml" "%DIST_DIR%\"
if exist "%BACKEND_DIR%\.env.example" (
    copy "%BACKEND_DIR%\.env.example" "%DIST_DIR%\.env"
)

echo [4/4] Copying frontend build...
xcopy /s /e /y "%FRONTEND_DIR%\dist" "%DIST_DIR%\frontend\"

echo.
echo === Build completed successfully! ===
echo.
echo Deployment files prepared in: %DIST_DIR%
echo.
echo Next steps:
echo   1. Copy dist/ contents to your server
echo   2. Set up environment variables in .env
echo   3. Install dependencies: pip install -e .
echo   4. Run: gunicorn app.main:app --host 0.0.0.0 --port 8000

endlocal
