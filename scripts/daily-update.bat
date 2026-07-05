@echo off
rem Gucci Intelligence - full daily update (08:00).
rem news scrap -> daily gucci (index+review) -> daily brief; Mondays add
rem product scan + weekly luxury. Finishes by publishing the static site.
cd /d C:\Users\andul\gucci-intel
set "ANTHROPIC_API_KEY="
for /f "usebackq tokens=2,*" %%A in (`reg query HKCU\Environment /v CLAUDE_CODE_OAUTH_TOKEN 2^>nul ^| find "CLAUDE_CODE_OAUTH_TOKEN"`) do set "CLAUDE_CODE_OAUTH_TOKEN=%%B"

set LOG=logs\daily-update.log
echo ================================================== >> %LOG%
echo [%date% %time%] daily update start >> %LOG%
rem Advertise the run to the app servers (web UI shows "running", blocks double-runs)
python -c "import json,datetime;open('logs/run.lock','w').write(json.dumps({'cmd':'daily-update','started':datetime.datetime.now().strftime('%%Y-%%m-%%d %%H:%%M:%%S'),'log':'daily-update.log'}))" >> %LOG% 2>&1

echo [%date% %time%] 1/3 news-scrap >> %LOG%
call claude -p "/news-scrap" --dangerously-skip-permissions >> %LOG% 2>&1

echo [%date% %time%] 2/3 daily-gucci >> %LOG%
call claude -p "/daily-gucci" --dangerously-skip-permissions >> %LOG% 2>&1

echo [%date% %time%] 3/3 daily-brief >> %LOG%
call claude -p "/daily-brief" --dangerously-skip-permissions >> %LOG% 2>&1

echo [%date% %time%] cd-watch (director desk) >> %LOG%
call claude -p "/cd-watch" --dangerously-skip-permissions >> %LOG% 2>&1

rem Special/Event desk cadence guard: a fresh deep-dive at least every 3 days
python -c "import glob,os,time,sys; fs=glob.glob('data/reports/special/*.md')+glob.glob('data/reports/events/*.md'); age=(time.time()-max((os.path.getmtime(f) for f in fs), default=0))/86400; print('special desk age(days): %%.1f' %% age); sys.exit(0 if age<3 else 1)" >> %LOG% 2>&1
if errorlevel 1 (
  echo [%date% %time%] special desk stale 3d+: running auto deep-dive >> %LOG%
  call claude -p "/gucci-special auto" --dangerously-skip-permissions >> %LOG% 2>&1
)

rem Mondays: refresh the product board and publish the weekly report
for /f %%D in ('powershell -NoProfile -Command "(Get-Date).DayOfWeek.value__"') do set DOW=%%D
if "%DOW%"=="1" (
  echo [%date% %time%] monday: gucci-products >> %LOG%
  call claude -p "/gucci-products" --dangerously-skip-permissions >> %LOG% 2>&1
  echo [%date% %time%] monday: weekly-luxury >> %LOG%
  call claude -p "/weekly-luxury" --dangerously-skip-permissions >> %LOG% 2>&1
)

del logs\run.lock 2>nul

echo [%date% %time%] retention cleanup (14d) >> %LOG%
python scripts\retention_cleanup.py >> %LOG% 2>&1

echo [%date% %time%] publish static site >> %LOG%
call scripts\publish-site.bat

echo [%date% %time%] daily update done >> %LOG%
