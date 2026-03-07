@echo off
title STTS - Speech to Text to Speech
echo Starting STTS...
echo.
echo The backend is running. Open http://localhost:5173 in your browser.
echo Press Ctrl+C to stop.
echo.
cd /d "%~dp0python\dist"
stts-backend.exe
pause
