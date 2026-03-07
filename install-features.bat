@echo off
setlocal enabledelayedexpansion
title STTS - Install Features
cd /d "%~dp0"

:: Check venv exists
if not exist "python\venv\Scripts\pip.exe" (
    echo [ERROR] Virtual environment not found. Run setup.bat first.
    pause
    exit /b 1
)

set PIP=python\venv\Scripts\pip.exe
set PYTHON=python\venv\Scripts\python.exe

:menu
cls
echo ==================================================
echo   STTS - Install Features
echo ==================================================
echo.

:: Show what's currently installed
echo   Checking installed features...
echo.

:: Check each feature
%PYTHON% -c "import faster_whisper" >nul 2>&1
if errorlevel 1 (set STT=NOT INSTALLED) else (set STT=INSTALLED)

%PYTHON% -c "import torch" >nul 2>&1
if errorlevel 1 (set TORCH=NOT INSTALLED) else (
    for /f "delims=" %%v in ('%PYTHON% -c "import torch; print(torch.__version__)" 2^>nul') do set TORCHVER=%%v
    set TORCH=INSTALLED [!TORCHVER!]
)

%PYTHON% -c "import transformers" >nul 2>&1
if errorlevel 1 (set TRANS=NOT INSTALLED) else (set TRANS=INSTALLED)

%PYTHON% -c "import llama_cpp" >nul 2>&1
if errorlevel 1 (set LLM=NOT INSTALLED) else (set LLM=INSTALLED)

%PYTHON% -c "import scipy" >nul 2>&1
if errorlevel 1 (set RVC=NOT INSTALLED) else (set RVC=INSTALLED)

%PYTHON% -c "import piper" >nul 2>&1
if errorlevel 1 (set PIPER=NOT INSTALLED) else (set PIPER=INSTALLED)

echo   [1] Speech-to-Text (Whisper)       - %STT%
echo   [2] PyTorch (CPU)                   - %TORCH%
echo   [3] PyTorch (CUDA - NVIDIA GPU)     - %TORCH%
echo   [4] Translation (NLLB)              - %TRANS%
echo   [5] Local LLM (llama.cpp)           - %LLM%
echo   [6] RVC Voice Conversion            - %RVC%
echo   [7] Piper TTS (offline TTS)         - %PIPER%
echo   [8] Install ALL (CPU)
echo   [9] Install ALL (CUDA - NVIDIA GPU)
echo.
echo   [0] Exit
echo.
set /p CHOICE="Choose an option: "

if "%CHOICE%"=="1" goto install_stt
if "%CHOICE%"=="2" goto install_torch_cpu
if "%CHOICE%"=="3" goto install_torch_cuda
if "%CHOICE%"=="4" goto install_translation
if "%CHOICE%"=="5" goto install_llm
if "%CHOICE%"=="6" goto install_rvc
if "%CHOICE%"=="7" goto install_piper
if "%CHOICE%"=="8" goto install_all_cpu
if "%CHOICE%"=="9" goto install_all_cuda
if "%CHOICE%"=="0" exit /b 0
goto menu

:install_stt
echo.
echo Installing Speech-to-Text (Whisper)...
%PIP% install -r python\requirements-stt.txt
if errorlevel 1 (echo [ERROR] Installation failed.) else (echo [OK] Done.)
pause
goto menu

:install_torch_cpu
echo.
echo Installing PyTorch (CPU only, ~200MB)...
%PIP% install torch --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 (echo [ERROR] Installation failed.) else (echo [OK] Done.)
pause
goto menu

:install_torch_cuda
echo.
echo Installing PyTorch (CUDA 12.1, ~2.5GB)...
echo This requires an NVIDIA GPU with up-to-date drivers.
%PIP% install torch --index-url https://download.pytorch.org/whl/cu121
if errorlevel 1 (echo [ERROR] Installation failed.) else (echo [OK] Done.)
pause
goto menu

:install_translation
echo.
:: Check for torch first
%PYTHON% -c "import torch" >nul 2>&1
if errorlevel 1 (
    echo [WARN] PyTorch is required for translation but not installed.
    set /p INST_TORCH="Install PyTorch CPU now? (Y/n): "
    if /i "!INST_TORCH!" neq "n" (
        echo Installing PyTorch CPU...
        %PIP% install torch --index-url https://download.pytorch.org/whl/cpu
    )
)
echo Installing Translation (NLLB)...
%PIP% install -r python\requirements-translation.txt
if errorlevel 1 (echo [ERROR] Installation failed.) else (echo [OK] Done.)
pause
goto menu

:install_llm
echo.
echo Installing Local LLM (llama.cpp)...
%PIP% install -r python\requirements-local-llm.txt
if errorlevel 1 (echo [ERROR] Installation failed.) else (echo [OK] Done.)
pause
goto menu

:install_rvc
echo.
:: Check for torch first
%PYTHON% -c "import torch" >nul 2>&1
if errorlevel 1 (
    echo [WARN] PyTorch is required for RVC but not installed.
    set /p INST_TORCH="Install PyTorch CPU now? (Y/n): "
    if /i "!INST_TORCH!" neq "n" (
        echo Installing PyTorch CPU...
        %PIP% install torch --index-url https://download.pytorch.org/whl/cpu
    )
)
echo Installing RVC Voice Conversion...
%PIP% install -r python\requirements-rvc.txt
if errorlevel 1 (echo [ERROR] Installation failed.) else (echo [OK] Done.)
pause
goto menu

:install_piper
echo.
echo Installing Piper TTS (offline TTS)...
%PIP% install -r python\requirements-tts-extra.txt
if errorlevel 1 (echo [ERROR] Installation failed.) else (echo [OK] Done.)
pause
goto menu

:install_all_cpu
echo.
echo Installing everything (CPU)... This may take a while.
echo.
echo [1/6] PyTorch CPU...
%PIP% install torch --index-url https://download.pytorch.org/whl/cpu
echo [2/6] Speech-to-Text...
%PIP% install -r python\requirements-stt.txt
echo [3/6] Translation...
%PIP% install -r python\requirements-translation.txt
echo [4/6] Local LLM...
%PIP% install -r python\requirements-local-llm.txt
echo [5/6] RVC Voice Conversion...
%PIP% install -r python\requirements-rvc.txt
echo [6/6] Piper TTS...
%PIP% install -r python\requirements-tts-extra.txt
echo.
echo [OK] All features installed (CPU).
pause
goto menu

:install_all_cuda
echo.
echo Installing everything (CUDA)... This may take a while.
echo.
echo [1/6] PyTorch CUDA...
%PIP% install torch --index-url https://download.pytorch.org/whl/cu121
echo [2/6] Speech-to-Text...
%PIP% install -r python\requirements-stt.txt
echo [3/6] Translation...
%PIP% install -r python\requirements-translation.txt
echo [4/6] Local LLM...
%PIP% install -r python\requirements-local-llm.txt
echo [5/6] RVC Voice Conversion...
%PIP% install -r python\requirements-rvc.txt
echo [6/6] Piper TTS...
%PIP% install -r python\requirements-tts-extra.txt
echo.
echo [OK] All features installed (CUDA).
pause
goto menu
