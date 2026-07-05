@echo off
rem Gucci Intelligence - daily news scrap (10 Gucci + 10 luxury)
rem Clears the exhausted watcher API key so claude uses subscription OAuth.
cd /d C:\Users\andul\gucci-intel
set "ANTHROPIC_API_KEY="
rem Load the long-lived token from the user registry in case the task inherits a stale env
for /f "usebackq tokens=2,*" %%A in (`reg query HKCU\Environment /v CLAUDE_CODE_OAUTH_TOKEN 2^>nul ^| find "CLAUDE_CODE_OAUTH_TOKEN"`) do set "CLAUDE_CODE_OAUTH_TOKEN=%%B"
echo [%date% %time%] news-scrap start >> logs\schtask-news.log
call claude -p "/news-scrap" --dangerously-skip-permissions >> logs\schtask-news.log 2>&1
echo [%date% %time%] news-scrap end (exit %errorlevel%) >> logs\schtask-news.log
