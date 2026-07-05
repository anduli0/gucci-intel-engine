@echo off
rem One-off: finish the 2026-07-05 cycle (step 3 + retention + publish).
cd /d C:\Users\andul\gucci-intel
set "ANTHROPIC_API_KEY="
for /f "usebackq tokens=2,*" %%A in (`reg query HKCU\Environment /v CLAUDE_CODE_OAUTH_TOKEN 2^>nul ^| find "CLAUDE_CODE_OAUTH_TOKEN"`) do set "CLAUDE_CODE_OAUTH_TOKEN=%%B"
set LOG=logs\daily-update.log
python -c "import json,datetime;open('logs/run.lock','w').write(json.dumps({'cmd':'daily-update','started':datetime.datetime.now().strftime('%%Y-%%m-%%d %%H:%%M:%%S'),'log':'daily-update.log'}))" >> %LOG% 2>&1
echo [%date% %time%] 3/3 daily-brief (finish) >> %LOG%
claude -p "/daily-brief" --dangerously-skip-permissions >> %LOG% 2>&1
del logs\run.lock 2>nul
echo [%date% %time%] retention cleanup (14d) >> %LOG%
python scripts\retention_cleanup.py >> %LOG% 2>&1
echo [%date% %time%] publish static site >> %LOG%
call scripts\publish-site.bat
echo [%date% %time%] daily update done >> %LOG%
