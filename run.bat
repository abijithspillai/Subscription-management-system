@echo off
setlocal
echo ========================================================
echo   Brightloop Software - Subscription Management System
echo   Odoo Cross Makeathon 9.0 (CUSAT)
echo ========================================================
echo.

set PYTHON_CMD=python
where python >nul 2>nul
if %ERRORLEVEL% neq 0 (
    if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
        set PYTHON_CMD="%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
    )
)

echo Starting Brightloop Application on http://127.0.0.1:5000 ...
%PYTHON_CMD% app.py

pause
