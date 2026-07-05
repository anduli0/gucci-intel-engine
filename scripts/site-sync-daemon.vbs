' Starts the site-sync daemon hidden (registered in the Startup folder).
CreateObject("WScript.Shell").Run "powershell -NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File ""C:\Users\andul\gucci-intel\scripts\site-sync-daemon.ps1""", 0, False
