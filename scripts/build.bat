@echo off
REM Folio release builder. All packaging logic is shared with Linux/macOS.
python "%~dp0build.py" %*
exit /b %errorlevel%
