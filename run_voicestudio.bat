@echo off
title VoiceStudio AI - Local Edition
echo ========================================================
echo Starting VoiceStudio AI (Local Edition)
echo Engine: OpenBMB VoxCPM2 ^| Device: Intel CPU
echo Host: http://127.0.0.1:7860
echo ========================================================

cd /d "D:\Coding\Rak'sTTS"
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
set HF_HOME=D:\Coding\Rak'sTTS\hf_cache

call .venv\Scripts\activate.bat
python -m app.main %*
pause
