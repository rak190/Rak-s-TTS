' VoiceStudio Pro — Silent Background Launcher (VBScript)
' Launches VoiceStudio Pro completely windowless in the background,
' with browser auto-opening at http://127.0.0.1:7860

Dim WshShell, FSO, ScriptDir, PythonExe, Cmd

Set WshShell = CreateObject("WScript.Shell")
Set FSO = CreateObject("Scripting.FileSystemObject")
ScriptDir = FSO.GetParentFolderName(WScript.ScriptFullName)

WshShell.CurrentDirectory = ScriptDir
WshShell.Environment("PROCESS")("PYTHONIOENCODING") = "utf-8"
WshShell.Environment("PROCESS")("PYTHONUTF8") = "1"
WshShell.Environment("PROCESS")("HF_HOME") = ScriptDir & "\hf_cache"

PythonExe = ScriptDir & "\.venv\Scripts\python.exe"

If Not FSO.FileExists(PythonExe) Then
    MsgBox "Python virtual environment not found at: " & PythonExe, 16, "VoiceStudio Pro - Error"
    WScript.Quit 1
End If

Cmd = """" & PythonExe & """ -m app.main"

' Run with window style 0 (hidden) and false (non-blocking)
WshShell.Run Cmd, 0, False
