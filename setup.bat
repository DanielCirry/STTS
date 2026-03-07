@echo off
setlocal enabledelayedexpansion
title STTS Setup
cd /d "%~dp0"

echo ==================================================
echo   STTS - First Time Setup
echo ==================================================
echo.

:: Check for Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not installed or not in PATH.
    echo.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation.
    echo.
    pause
    exit /b 1
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo [OK] Found Python %PYVER%

:: Check if venv already exists
if exist "python\venv\Scripts\python.exe" (
    echo [OK] Virtual environment already exists.
    set /p RECREATE="Recreate it? (y/N): "
    if /i "!RECREATE!" neq "y" goto install_base
    echo Removing old venv...
    rmdir /s /q "python\venv"
)

:: Create venv
echo.
echo Creating virtual environment...
python -m venv python\venv
if errorlevel 1 (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
)
echo [OK] Virtual environment created.

:: Upgrade pip
echo Upgrading pip...
python\venv\Scripts\python.exe -m pip install --upgrade pip --quiet

:install_base
echo.
echo Installing base dependencies...
python\venv\Scripts\pip.exe install -r python\requirements-base.txt --quiet
if errorlevel 1 (
    echo [ERROR] Failed to install base dependencies.
    pause
    exit /b 1
)
echo [OK] Base dependencies installed.

:: Build frontend if node is available
if exist "dist\index.html" (
    echo [OK] Frontend already built.
) else (
    node --version >nul 2>&1
    if errorlevel 1 (
        echo [WARN] Node.js not found - cannot build frontend.
        echo        You need a pre-built dist\ folder to run STTS.
    ) else (
        echo Building frontend...
        call npx vite build --quiet
        if exist "dist\index.html" (
            echo [OK] Frontend built.
        ) else (
            echo [WARN] Frontend build may have failed.
        )
    )
)

echo.
echo ==================================================
echo   Setup complete!
echo ==================================================
echo.
echo   Run STTS:            Start-STTS.bat
echo   Install extras:      install-features.bat
echo.
pause
