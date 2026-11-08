# ==============================================================================
# VoiceStudio AI - Windows Desktop Shortcut Creator
# Creates a personalized, high-resolution desktop shortcut with custom icon
# ==============================================================================

$WshShell = New-Object -ComObject WScript.Shell
$DesktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
if (-not $DesktopPath -or -not (Test-Path $DesktopPath)) {
    $DesktopPath = "C:\Users\Admin\Desktop"
}

$ProjectDir = "D:\Coding\Rak'sTTS"
$ShortcutPath = Join-Path $DesktopPath "VoiceStudio AI.lnk"
$TargetBat = Join-Path $ProjectDir "run_voicestudio.bat"
$IconPath = Join-Path $ProjectDir "assets\voicestudio.ico"

Write-Host "Creating Windows Desktop Shortcut for VoiceStudio AI..." -ForegroundColor Cyan

if (-not (Test-Path $TargetBat)) {
    Write-Error "Launcher batch file not found at: $TargetBat"
    exit 1
}

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $TargetBat
$Shortcut.WorkingDirectory = $ProjectDir
if (Test-Path $IconPath) {
    $Shortcut.IconLocation = "$IconPath, 0"
}
$Shortcut.Description = "VoiceStudio AI - Multilingual Speech and Voice Cloning Studio"
$Shortcut.WindowStyle = 1
$Shortcut.Save()

Write-Host "SUCCESS: Desktop shortcut created successfully!" -ForegroundColor Green
Write-Host "Location: $ShortcutPath" -ForegroundColor White
Write-Host "You can now double-click 'VoiceStudio AI' on your Desktop to launch the studio." -ForegroundColor Yellow
