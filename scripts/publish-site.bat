@echo off
rem Export a fresh static snapshot and push it to the FIXED site URL repo
rem (anduli0.github.io/gucci-intel-site).
cd /d C:\Users\andul\gucci-intel
set "EXPORT_OUT=C:\Users\andul\gucci-intel-site"
python scripts\export_static.py >> logs\publish-site.log 2>&1
cd /d C:\Users\andul\gucci-intel-site
git add -A >> C:\Users\andul\gucci-intel\logs\publish-site.log 2>&1
git -c user.name="anduli0" -c user.email="minkyu494@gmail.com" commit -m "local publish %date% %time%" >> C:\Users\andul\gucci-intel\logs\publish-site.log 2>&1
git -c user.name="anduli0" -c user.email="minkyu494@gmail.com" pull --rebase origin main >> C:\Users\andul\gucci-intel\logs\publish-site.log 2>&1
git push >> C:\Users\andul\gucci-intel\logs\publish-site.log 2>&1
