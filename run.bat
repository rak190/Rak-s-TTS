@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
title VoiceStudio Pro - Apple Creative Workspace

cd /d "%~dp0"

set "PYTHONIOENCODING=utf-8"
set "PYTHONUTF8=1"
set "HF_HOME=%~dp0hf_cache"
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"

if not exist "!PYTHON_EXE!" (
    echo.
    echo  [ERROR] Python virtual environment was not found at .venv\Scripts\python.exe
    echo  Please ensure the virtual environment is installed in this project directory.
    echo.
    pause
    exit /b 1
)

:: Check for direct command-line arguments
if "%~1"=="--now" goto launch_standard
if "%~1"=="--fast" goto launch_fast
if "%~1"=="--silent" goto launch_silent
if "%~1"=="--shortcut" goto make_shortcut
if "%~1"=="--test" goto run_tests
if "%~1"=="-h" goto show_help
if "%~1"=="--help" goto show_help

:: If any custom arguments are passed (e.g. --port 7861), pass directly to main.py
if not "%~1"=="" (
    "!PYTHON_EXE!" -m app.main %*
    exit /b !ERRORLEVEL!
)

:menu_loop
cls
echo  ==============================================================================
echo    VOICESTUDIO PRO  -  Apple Creative Workspace and Multi-Speaker TTS Studio
echo    Engine: OpenBMB VoxCPM2  ^|  Native Audio: 48kHz  ^|  Intel Core i5 CPU
echo  ==============================================================================
echo.
echo     [1]   Start VoiceStudio Pro        (Standard start - Auto-open browser)
echo     [2]   Fast Boot (Headless)         (Skip browser launch - Console only)
echo     [3]   Create Desktop Shortcuts     (Desktop + Start Menu with Studio Icon)
echo     [4]   Run Test Suite               (Fast smart regression test suite)
echo     [5]   Start in Background          (Silent launch - No terminal window)
echo     [Q]   Exit
echo.
echo  ------------------------------------------------------------------------------
echo   Auto-launching in 3 seconds... (Press [1-5] or [Q] to choose, or Enter to start)

choice /c 12345Q /n /t 3 /d 1 >nul
set "CHOICE_VAL=%ERRORLEVEL%"

if "%CHOICE_VAL%"=="1" goto launch_standard
if "%CHOICE_VAL%"=="2" goto launch_fast
if "%CHOICE_VAL%"=="3" goto make_shortcut
if "%CHOICE_VAL%"=="4" goto run_tests
if "%CHOICE_VAL%"=="5" goto launch_silent
if "%CHOICE_VAL%"=="6" goto exit_launcher

goto launch_standard

:launch_standard
echo.
echo  Starting VoiceStudio Pro...
echo  Local Studio: http://127.0.0.1:7860
echo  Press Ctrl+C in this console to stop the server at any time.
echo.
"!PYTHON_EXE!" -m app.main
set "EXIT_CODE=%ERRORLEVEL%"
if %EXIT_CODE% neq 0 (
    echo.
    echo  [NOTICE] VoiceStudio Pro closed with status code %EXIT_CODE%.
    pause
)
exit /b %EXIT_CODE%

:launch_fast
echo.
echo  Fast Booting VoiceStudio Pro (Headless / No Browser)...
echo  Local Studio: http://127.0.0.1:7860
echo.
"!PYTHON_EXE!" -m app.main --no-browser
set "EXIT_CODE=%ERRORLEVEL%"
if %EXIT_CODE% neq 0 (
    echo.
    echo  [NOTICE] VoiceStudio Pro closed with status code %EXIT_CODE%.
    pause
)
exit /b %EXIT_CODE%

:launch_silent
echo.
echo  Launching VoiceStudio Pro silently in the background...
if exist "run_silent.vbs" (
    wscript.exe "%~dp0run_silent.vbs"
    echo  VoiceStudio Pro started in background.
    echo  Opening http://127.0.0.1:7860 in your default browser...
    timeout /t 2 >nul
    exit /b 0
) else (
    start "" /b "!PYTHON_EXE!" -m app.main
    echo  VoiceStudio Pro started in background.
    exit /b 0
)

:make_shortcut
echo.
echo  Creating Windows Desktop and Start Menu Shortcuts...
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0create_desktop_shortcut.ps1"
echo.
echo  Press any key to return to menu...
pause >nul
goto menu_loop

:run_tests
echo.
echo  Running Fast Smart Test Suite...
echo.
"!PYTHON_EXE!" -m unittest tests/test_database.py tests/test_ui_api.py tests/test_batch_queue.py tests/test_smart_script_studio.py tests/test_desktop_launcher.py -v
echo.
echo  Press any key to return to menu...
pause >nul
goto menu_loop

:show_help
echo.
echo VoiceStudio Pro Launcher Commands:
echo   run.bat                 Open interactive launcher with 3s auto-start
echo   run.bat --now           Start studio immediately (standard mode)
echo   run.bat --fast          Start studio headless (skip browser)
echo   run.bat --silent        Start studio in background (no CMD window)
echo   run.bat --shortcut      Create Desktop and Start Menu shortcuts
echo   run.bat --test          Run automated regression test suite
echo.
exit /b 0

:exit_launcher
echo.
echo  Goodbye!
exit /b 0
