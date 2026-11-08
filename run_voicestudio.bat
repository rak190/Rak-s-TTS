@echo off
setlocal enabledelayedexpansion
title VoiceStudio AI - Studio Edition

echo ==============================================================================
echo   VoiceStudio AI - Multilingual Speech and Voice Cloning Studio
echo   Engine: OpenBMB VoxCPM2 ^| Device: Intel Core i5 CPU ^| Host: 127.0.0.1:7860
echo ==============================================================================
echo.

cd /d "%~dp0"

set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "HF_HOME=%~dp0hf_cache"

if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] Python virtual environment was not found at .venv\Scripts\python.exe
    echo Please make sure the virtual environment is installed before running.
    echo.
    pause
    exit /b 1
)

call .venv\Scripts\activate.bat

python -m app.main %*
set "EXITCODE=%ERRORLEVEL%"

if %EXITCODE% neq 0 (
    echo.
    echo [NOTICE] Application closed with status code %EXITCODE%.
    pause
)

exit /b %EXITCODE%
