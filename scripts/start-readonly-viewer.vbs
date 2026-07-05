' Starts the Gucci Intelligence READ-ONLY viewer server (port 8791) hidden.
' Registered as a logon scheduled task so the public Tailscale share survives reboots.
CreateObject("WScript.Shell").Run "pythonw ""C:\Users\andul\gucci-intel\app\server.py"" --readonly --port 8791", 0, False
