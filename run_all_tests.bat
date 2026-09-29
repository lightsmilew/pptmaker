@echo off
REM Run all tests (backend + frontend) for PPTMaker

echo ============================================
echo  PPTMaker - Full Test Suite
echo ============================================
echo.

REM --- Backend tests ---
echo [1/2] Running backend tests...
echo ----------------------------------------
cd /d "%~dp0backend"
call python -m pytest --tb=short -q
set BACKEND_EXIT=%ERRORLEVEL%
echo.

REM --- Frontend tests ---
echo [2/2] Running frontend tests...
echo ----------------------------------------
cd /d "%~dp0frontend"
call npx vitest run
set FRONTEND_EXIT=%ERRORLEVEL%
echo.

REM --- Summary ---
echo ============================================
echo  Summary
echo ============================================
if %BACKEND_EXIT% EQU 0 (
    echo  Backend:  PASSED
) else (
    echo  Backend:  FAILED ^(exit %BACKEND_EXIT%^)
)
if %FRONTEND_EXIT% EQU 0 (
    echo  Frontend: PASSED
) else (
    echo  Frontend: FAILED ^(exit %FRONTEND_EXIT%^)
)
echo.

if %BACKEND_EXIT% NEQ 0 exit /b %BACKEND_EXIT%
if %FRONTEND_EXIT% NEQ 0 exit /b %FRONTEND_EXIT%
exit /b 0
