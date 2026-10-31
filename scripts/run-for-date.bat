@echo off
rem Gucci Intelligence - run the daily cycle for an EXPLICIT date (catch-up / re-run).
rem Usage: scripts\run-for-date.bat 2026-10-31 [skip-news]
rem Same steps as daily-update.bat but every command gets the date, so a run that
rem crosses midnight still produces reports for the intended day.
cd /d C:\Users\andul\gucci-intel
set "ANTHROPIC_API_KEY="
set "CLAUDE_CODE_OAUTH_TOKEN="
set D=%1
if "%D%"=="" (echo usage: run-for-date.bat YYYY-MM-DD & exit /b 2)
set LOG=logs\daily-update.log
echo ================================================== >> %LOG%
echo [%date% %time%] catch-up run for %D% start >> %LOG%
python -c "import json,datetime;open('logs/run.lock','w').write(json.dumps({'cmd':'run-for-date %D%','started':datetime.datetime.now().strftime('%%Y-%%m-%%d %%H:%%M')}))"

if not "%2"=="skip-news" (
  echo [%date% %time%] 1/3 news-scrap %D% >> %LOG%
  call claude -p "/news-scrap %D%" --dangerously-skip-permissions >> %LOG% 2>&1
)

python scripts\collect_engagement.py %D% >> %LOG% 2>&1
python scripts\collect_buzz.py %D% >> %LOG% 2>&1
python scripts\collect_sov.py %D% >> %LOG% 2>&1
echo [%date% %time%] 2/3 daily-gucci %D% >> %LOG%
call claude -p "/daily-gucci %D%" --dangerously-skip-permissions >> %LOG% 2>&1

echo [%date% %time%] 3/3 daily-brief %D% >> %LOG%
call claude -p "/daily-brief %D%" --dangerously-skip-permissions >> %LOG% 2>&1

for /f %%W in ('powershell -NoProfile -Command "([datetime]'%D%').DayOfWeek.value__"') do set DOW=%%W
if "%DOW%"=="5" (
  echo [%date% %time%] friday: weekly-review %D% >> %LOG%
  call claude -p "/weekly-review %D%" --dangerously-skip-permissions >> %LOG% 2>&1
)

del logs\run.lock 2>nul
echo [%date% %time%] publish static site >> %LOG%
call scripts\publish-site.bat
echo [%date% %time%] catch-up run for %D% done >> %LOG%
