@echo off
title EchoLife — Lifelong Voice Identity
color 0F

echo ========================================================
echo        ECHOLIFE: LIFELONG DIGITAL VOICE IDENTITY
echo      100%% Offline * Privacy-First * On-Device AI
echo ========================================================
echo.

:: Redirect temp directories to D: drive (38GB free) to prevent C: drive out-of-space errors
set "TEMP=D:\pip_temp"
set "TMP=D:\pip_temp"
set "PIP_CACHE_DIR=D:\pip_cache"

if not exist "D:\pip_temp" mkdir "D:\pip_temp"
if not exist "D:\pip_cache" mkdir "D:\pip_cache"

:: Use the virtual environment on D: drive
if not exist "D:\Echolife\.venv" (
    echo [1/4] Creating virtual environment on D: drive...
    py -3.11 -m venv D:\Echolife\.venv
)

call "D:\Echolife\.venv\Scripts\activate.bat"

echo [2/4] Checking PyTorch (CUDA acceleration for RTX 4050)...
python -c "import torch; print('PyTorch loaded, CUDA:', torch.cuda.is_available())" >nul 2>&1
if %errorlevel% neq 0 (
    echo PyTorch not detected. Installing PyTorch with CUDA 12.1 support...
    python -m pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
)

echo [3/4] Checking backend dependencies...
python -c "import fastapi, soundfile, cryptography" >nul 2>&1
if %errorlevel% neq 0 (
    echo Installing backend core dependencies...
    python -m pip install -r backend/requirements.txt
)

echo [4/4] Launching EchoLife Local Server...
start "" "http://127.0.0.1:8000"
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000 --reload

pause
