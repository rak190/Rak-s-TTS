# ==============================================================================
# VoiceStudio Pro - Local Desktop Launcher (PowerShell)
# ==============================================================================
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = "VoiceStudio Pro — Apple Creative Workspace"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ScriptDir) {
    $ScriptDir = "D:\Coding\Rak'sTTS"
}
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

# Check for CLI flags
if ($args -contains "--silent") {
    $SilentVbs = Join-Path $ScriptDir "run_silent.vbs"
    if (Test-Path $SilentVbs) {
        Start-Process "wscript.exe" -ArgumentList "`"$SilentVbs`""
        Write-Host "✅ VoiceStudio Pro launched in background." -ForegroundColor Green
        exit 0
    }
}

if ($args -contains "--shortcut") {
    $ShortcutScript = Join-Path $ScriptDir "create_desktop_shortcut.ps1"
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $ShortcutScript
    exit 0
}

Write-Host "  ╭────────────────────────────────────────────────────────────────────────╮" -ForegroundColor Magenta
Write-Host "  │   🎙️  VOICESTUDIO PRO   •   Apple Creative Workspace & Multi-Speaker TTS     │" -ForegroundColor Cyan
Write-Host "  │   Engine: OpenBMB VoxCPM2  │  Native Audio: 48kHz  │  Intel Core i5 CPU    │" -ForegroundColor DarkGray
Write-Host "  ╰────────────────────────────────────────────────────────────────────────╯" -ForegroundColor Magenta
Write-Host ""
Write-Host "🚀 Launching VoiceStudio Pro..." -ForegroundColor Green
Write-Host "Local Studio: http://127.0.0.1:7860" -ForegroundColor White
Write-Host "Press Ctrl+C in this console to stop the server at any time." -ForegroundColor DarkGray
Write-Host ""

& $PythonExe -m app.main $args
$ExitCode = $LASTEXITCODE

if ($ExitCode -ne 0) {
    Write-Host ""
    Write-Host "[NOTICE] VoiceStudio Pro closed with status code $ExitCode" -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
}

exit $ExitCode
