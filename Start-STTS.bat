@echo off
setlocal
title STTS - Speech to Text to Speech
cd /d "%~dp0"

:: Lock file
set "LOCKFILE=%TEMP%\stts-launcher.lock"
if exist "%LOCKFILE%" (
    netstat -an 2>nul | find "9876" | find "LISTENING" >nul
    if not errorlevel 1 (
        echo STTS is already running!
        pause
        exit /b 1
    )
    del "%LOCKFILE%" 2>nul
)
echo %DATE% %TIME% > "%LOCKFILE%"

echo ==================================================
echo   STTS - Speech to Text to Speech
echo ==================================================
echo.

:: Check venv
if not exist "python\venv\Scripts\python.exe" (
    echo [ERROR] Virtual environment not found.
    echo         Run setup.bat first.
    del "%LOCKFILE%" 2>nul
    pause
    exit /b 1
)

:: Check frontend
if not exist "dist\index.html" (
    echo [ERROR] Frontend not built.
    echo         Run setup.bat first or build with: npx vite build
    del "%LOCKFILE%" 2>nul
    pause
    exit /b 1
)

:: Start backend
echo Starting backend...
start "STTS-Backend" /min python\venv\Scripts\python.exe python\main.py

:: Wait for backend
echo Waiting for backend to start...
:wait_backend
timeout /t 1 /nobreak >nul
netstat -an | find "9876" | find "LISTENING" >nul
if errorlevel 1 goto wait_backend
echo [OK] Backend ready on port 9876

:: Start frontend server
echo Starting frontend...
start "STTS-Frontend" /min python\venv\Scripts\python.exe -m http.server 5173 --bind 127.0.0.1 --directory dist

:: Wait for frontend
:wait_frontend
timeout /t 1 /nobreak >nul
netstat -an | find "5173" | find "LISTENING" >nul
if errorlevel 1 goto wait_frontend
echo [OK] Frontend ready on port 5173

:: Open browser
echo.
start http://localhost:5173

echo ==================================================
echo   STTS is running!
echo   Press any key to stop.
echo ==================================================
echo.
pause >nul

:: Cleanup
echo Shutting down...
del "%LOCKFILE%" 2>nul
taskkill /FI "WINDOWTITLE eq STTS-Backend*" /F >nul 2>&1
taskkill /FI "WINDOWTITLE eq STTS-Frontend*" /F >nul 2>&1
echo Done.
exit /b 0
