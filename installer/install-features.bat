@echo off
setlocal enabledelayedexpansion
title STTS - Install Features
cd /d "%~dp0"

echo Checking for Python...
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

:: Create venv if it doesn't exist
if not exist "venv\Scripts\pip.exe" (
    echo Creating virtual environment for extra packages...
    python -m venv venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
    venv\Scripts\python.exe -m pip install --upgrade pip --quiet
    echo [OK] Virtual environment created.
    echo.
)

set PIP=venv\Scripts\pip.exe
set PYTHON=venv\Scripts\python.exe

:menu
cls
echo ==================================================
echo   STTS - Install Features
echo ==================================================
echo.
echo   Checking installed features...
echo.

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
%PIP% install faster-whisper>=1.0.0 ctranslate2>=4.0.0
goto done

:install_torch_cpu
echo.
echo Installing PyTorch (CPU only, ~200MB)...
%PIP% install torch --index-url https://download.pytorch.org/whl/cpu
goto done

:install_torch_cuda
echo.
echo Installing PyTorch (CUDA 12.1, ~2.5GB)...
echo This requires an NVIDIA GPU with up-to-date drivers.
%PIP% install torch --index-url https://download.pytorch.org/whl/cu121
goto done

:install_translation
echo.
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
%PIP% install transformers>=4.35.0 sentencepiece>=0.1.99
goto done

:install_llm
echo.
echo Installing Local LLM (llama.cpp)...
%PIP% install llama-cpp-python>=0.2.50
goto done

:install_rvc
echo.
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
%PIP% install scipy>=1.10.0 faiss-cpu>=1.7.3 "librosa>=0.9.2,<0.11.0" soundfile>=0.12.1 pydub>=0.25.1
goto done

:install_piper
echo.
echo Installing Piper TTS (offline TTS)...
%PIP% install piper-tts>=1.2.0 onnxruntime>=1.16.0
goto done

:install_all_cpu
echo.
echo Installing everything (CPU)... This may take a while.
echo.
echo [1/6] PyTorch CPU...
%PIP% install torch --index-url https://download.pytorch.org/whl/cpu
echo [2/6] Speech-to-Text...
%PIP% install faster-whisper>=1.0.0 ctranslate2>=4.0.0
echo [3/6] Translation...
%PIP% install transformers>=4.35.0 sentencepiece>=0.1.99
echo [4/6] Local LLM...
%PIP% install llama-cpp-python>=0.2.50
echo [5/6] RVC Voice Conversion...
%PIP% install scipy>=1.10.0 faiss-cpu>=1.7.3 "librosa>=0.9.2,<0.11.0" soundfile>=0.12.1 pydub>=0.25.1
echo [6/6] Piper TTS...
%PIP% install piper-tts>=1.2.0 onnxruntime>=1.16.0
echo.
echo [OK] All features installed (CPU).
goto done

:install_all_cuda
echo.
echo Installing everything (CUDA)... This may take a while.
echo.
echo [1/6] PyTorch CUDA...
%PIP% install torch --index-url https://download.pytorch.org/whl/cu121
echo [2/6] Speech-to-Text...
%PIP% install faster-whisper>=1.0.0 ctranslate2>=4.0.0
echo [3/6] Translation...
%PIP% install transformers>=4.35.0 sentencepiece>=0.1.99
echo [4/6] Local LLM...
%PIP% install llama-cpp-python>=0.2.50
echo [5/6] RVC Voice Conversion...
%PIP% install scipy>=1.10.0 faiss-cpu>=1.7.3 "librosa>=0.9.2,<0.11.0" soundfile>=0.12.1 pydub>=0.25.1
echo [6/6] Piper TTS...
%PIP% install piper-tts>=1.2.0 onnxruntime>=1.16.0
echo.
echo [OK] All features installed (CUDA).
goto done

:done
if errorlevel 1 (echo [ERROR] Installation failed.) else (echo [OK] Done.)
pause
goto menu
