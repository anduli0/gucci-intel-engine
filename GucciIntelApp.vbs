' Gucci Intelligence desktop app launcher.
' Starts the local server (hidden) if it is not already running,
' waits until it answers, then opens the dashboard in an Edge app window.
Option Explicit
Dim sh, fso, root, edge, i

Set sh = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
root = fso.GetParentFolderName(WScript.ScriptFullName)

Function ServerAlive()
    Dim xhr
    ServerAlive = False
    On Error Resume Next
    Set xhr = CreateObject("MSXML2.XMLHTTP")
    xhr.Open "GET", "http://127.0.0.1:8790/api/status", False
    xhr.Send
    If Err.Number = 0 Then
        If xhr.Status = 200 Then ServerAlive = True
    End If
    Err.Clear
    On Error GoTo 0
End Function

If Not ServerAlive() Then
    ' pythonw = fully windowless; fall back to hidden python if missing
    On Error Resume Next
    sh.Run "pythonw """ & root & "\app\server.py""", 0, False
    If Err.Number <> 0 Then
        Err.Clear
        sh.Run "python """ & root & "\app\server.py""", 0, False
    End If
    On Error GoTo 0
    ' wait up to 10 seconds for the server to answer
    For i = 1 To 20
        WScript.Sleep 500
        If ServerAlive() Then Exit For
    Next
End If

If Not ServerAlive() Then
    MsgBox "Gucci Intelligence server failed to start." & vbCrLf & _
           "Check logs\app-server.log in " & root, vbExclamation, "Gucci Intelligence"
    WScript.Quit 1
End If

edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
If Not fso.FileExists(edge) Then edge = "C:\Program Files\Microsoft\Edge\Application\msedge.exe"

If fso.FileExists(edge) Then
    ' --start-maximized: open fitted to the screen instead of a fixed size
    sh.Run """" & edge & """ --app=http://127.0.0.1:8790/ --start-maximized", 3, False
Else
    sh.Run "http://127.0.0.1:8790/", 3, False
End If
