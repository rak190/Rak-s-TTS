# ==============================================================================
# VoiceStudio AI - Local Desktop Launcher (PowerShell)
# ==============================================================================
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = "VoiceStudio AI - Studio Edition"

Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host "  VoiceStudio AI - Multilingual Speech and Voice Cloning Studio" -ForegroundColor Cyan
Write-Host "  Engine: OpenBMB VoxCPM2 | Device: Intel Core i5 CPU | Host: 127.0.0.1:7860" -ForegroundColor Cyan
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host ""

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
$env:HF_HOME = Join-Path $ScriptDir "hf_cache"

$PythonExe = Join-Path $ScriptDir ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    Write-Host "[ERROR] Python virtual environment was not found at $PythonExe" -ForegroundColor Red
    Write-Host "Please ensure the virtual environment is installed." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

& $PythonExe -m app.main $args
$ExitCode = $LASTEXITCODE

if ($ExitCode -ne 0) {
    Write-Host ""
    Write-Host "[NOTICE] Application exited with status code $ExitCode" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
}

exit $ExitCode
