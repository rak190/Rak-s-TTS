# VoiceStudio AI Local Launcher (PowerShell)
$Host.UI.RawUI.WindowTitle = "VoiceStudio AI - Local Edition"
Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "Starting VoiceStudio AI (Local Edition)" -ForegroundColor Cyan
Write-Host "Engine: OpenBMB VoxCPM2 | Device: Intel CPU (4 Threads)" -ForegroundColor Cyan
Write-Host "Host: http://127.0.0.1:7860" -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

Set-Location "D:\Coding\Rak'sTTS"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
$env:HF_HOME = "D:\Coding\Rak'sTTS\hf_cache"

& ".\.venv\Scripts\python.exe" -m app.main $args
