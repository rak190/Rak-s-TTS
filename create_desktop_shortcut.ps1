# ==============================================================================
# VoiceStudio Pro - Windows Desktop & Start Menu Shortcut Creator
# Creates personalized, high-resolution shortcuts with custom studio icon
# ==============================================================================

$WshShell = New-Object -ComObject WScript.Shell
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ProjectDir) {
    $ProjectDir = "D:\Coding\Rak'sTTS"
}

# 1. Resolve Target Executable / Batch Runner
$TargetBat = Join-Path $ProjectDir "run.bat"
if (-not (Test-Path $TargetBat)) {
    $TargetBat = Join-Path $ProjectDir "run_voicestudio.bat"
}

# 2. Resolve High-Res Studio Icon
$IconPath = Join-Path $ProjectDir "assets\voicestudio.ico"
if (-not (Test-Path $IconPath)) {
    $IconPath = Join-Path $ProjectDir "voicestudio.ico"
}

Write-Host "==============================================================================" -ForegroundColor Magenta
Write-Host "  VoiceStudio Pro - Shortcut Installer" -ForegroundColor Cyan
Write-Host "==============================================================================" -ForegroundColor Magenta

# 3. Create Desktop Shortcut
$DesktopPath = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Desktop)
if (-not $DesktopPath -or -not (Test-Path $DesktopPath)) {
    $DesktopPath = Join-Path $env:USERPROFILE "Desktop"
}
$DesktopShortcutPath = Join-Path $DesktopPath "VoiceStudio Pro.lnk"

$DesktopShortcut = $WshShell.CreateShortcut($DesktopShortcutPath)
$DesktopShortcut.TargetPath = $TargetBat
$DesktopShortcut.WorkingDirectory = $ProjectDir
if (Test-Path $IconPath) {
    $DesktopShortcut.IconLocation = "$IconPath, 0"
}
$DesktopShortcut.Description = "VoiceStudio Pro - Apple Creative Workspace and Multi-Speaker TTS"
$DesktopShortcut.WindowStyle = 1
$DesktopShortcut.Save()

Write-Host "  [OK] Desktop Shortcut Created:" -ForegroundColor Green
Write-Host "       $DesktopShortcutPath" -ForegroundColor White

# 4. Create Start Menu Shortcut
$StartMenuPrograms = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Programs)
if (-not $StartMenuPrograms -or -not (Test-Path $StartMenuPrograms)) {
    $StartMenuPrograms = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs"
}

if (Test-Path $StartMenuPrograms) {
    $StartMenuShortcutPath = Join-Path $StartMenuPrograms "VoiceStudio Pro.lnk"
    $StartMenuShortcut = $WshShell.CreateShortcut($StartMenuShortcutPath)
    $StartMenuShortcut.TargetPath = $TargetBat
    $StartMenuShortcut.WorkingDirectory = $ProjectDir
    if (Test-Path $IconPath) {
        $StartMenuShortcut.IconLocation = "$IconPath, 0"
    }
    $StartMenuShortcut.Description = "VoiceStudio Pro - Apple Creative Workspace and Multi-Speaker TTS"
    $StartMenuShortcut.WindowStyle = 1
    $StartMenuShortcut.Save()

    Write-Host "  [OK] Start Menu Shortcut Created:" -ForegroundColor Green
    Write-Host "       $StartMenuShortcutPath" -ForegroundColor White
}

Write-Host ""
Write-Host "VoiceStudio Pro is now accessible from your Desktop and Start Menu!" -ForegroundColor Cyan
Write-Host "Double-click 'VoiceStudio Pro' to start the studio with 1-click." -ForegroundColor Gray
