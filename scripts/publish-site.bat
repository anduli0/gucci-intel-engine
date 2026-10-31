@echo off
rem Export a fresh static snapshot and push it to the FIXED site URL repo
rem (anduli0.github.io/gucci-intel-site).
rem The cloud (publish-only / daily.yml) is the primary publisher; this PC path
rem is the fallback. Generated files conflict on every rebase, so the site clone
rem is first aligned to origin/main (origin wins), THEN the export is written on
rem top and pushed. Never leaves the clone in a detached/rebasing state.
set LOG=C:\Users\andul\gucci-intel\logs\publish-site.log
cd /d C:\Users\andul\gucci-intel-site
echo [%date% %time%] publish start >> %LOG%
git rebase --abort >nul 2>&1
git merge --abort >nul 2>&1
git checkout -q main >> %LOG% 2>&1
git fetch -q origin >> %LOG% 2>&1
git -c user.name="anduli0" -c user.email="minkyu494@gmail.com" merge -q -X theirs origin/main -m "sync to cloud publish" >> %LOG% 2>&1
git checkout origin/main -- . >> %LOG% 2>&1
cd /d C:\Users\andul\gucci-intel
set "EXPORT_OUT=C:\Users\andul\gucci-intel-site"
python scripts\export_static.py >> %LOG% 2>&1
if errorlevel 1 (
  echo [%date% %time%] export failed - not publishing >> %LOG%
  exit /b 1
)
cd /d C:\Users\andul\gucci-intel-site
git add -A >> %LOG% 2>&1
git -c user.name="anduli0" -c user.email="minkyu494@gmail.com" commit -q -m "local publish %date% %time%" >> %LOG% 2>&1
git push origin main >> %LOG% 2>&1
if errorlevel 1 (
  rem cloud pushed in between: take origin, re-export on top, push once more
  git fetch -q origin >> %LOG% 2>&1
  git -c user.name="anduli0" -c user.email="minkyu494@gmail.com" merge -q -X theirs origin/main -m "sync to cloud publish" >> %LOG% 2>&1
  git checkout origin/main -- . >> %LOG% 2>&1
  cd /d C:\Users\andul\gucci-intel
  python scripts\export_static.py >> %LOG% 2>&1
  cd /d C:\Users\andul\gucci-intel-site
  git add -A >> %LOG% 2>&1
  git -c user.name="anduli0" -c user.email="minkyu494@gmail.com" commit -q -m "local publish %date% %time% (retry)" >> %LOG% 2>&1
  git push origin main >> %LOG% 2>&1
)
echo [%date% %time%] publish end >> %LOG%
