' ============================================================
'  Black Window Eliminator for Windows Task Scheduler
'
'  WHY THIS EXISTS:
'  - .bat/.ps1 run via Task Scheduler with InteractiveToken shows a visible cmd window
'  - Manually closing the window sends CTRL_CLOSE signal = KeyboardInterrupt in Python
'  - This kills the entire task tree with exit code 0xC000013A
'
'  SOLUTION:
'  - VBScript runs under wscript.exe (GUI subsystem, no console)
'  - Launches bat/ps1 via cmd /c with window style 0 (hidden)
'  - Window never appears -> cannot be closed -> task runs to completion
'
'  Usage: wscript run_hidden.vbs "<script_absolute_path>"
'  Exit codes: 2=missing argument, 3=script not found, else=passthrough from script
' ============================================================
Option Explicit
Dim sh, fso, script, ec
If WScript.Arguments.Count < 1 Then WScript.Quit 2
script = WScript.Arguments(0)
Set fso = CreateObject("Scripting.FileSystemObject")
If Not fso.FileExists(script) Then WScript.Quit 3
Set sh = CreateObject("WScript.Shell")
' Second param 0 = hide window; True = wait for completion (Task Scheduler gets correct exit code)
ec = sh.Run("cmd /c """ & script & """", 0, True)
WScript.Quit ec
