@echo off
rem Export a fresh static snapshot and push it to GitHub Pages.
cd /d C:\Users\andul\gucci-intel
python scripts\export_static.py >> logs\publish-site.log 2>&1
cd /d C:\Users\andul\gucci-intel-site
git pull --rebase origin main >> C:\Users\andul\gucci-intel\logs\publish-site.log 2>&1
git add -A >> C:\Users\andul\gucci-intel\logs\publish-site.log 2>&1
git -c user.name="anduli0" -c user.email="minkyu494@gmail.com" commit -m "auto update %date% %time%" >> C:\Users\andul\gucci-intel\logs\publish-site.log 2>&1
git push >> C:\Users\andul\gucci-intel\logs\publish-site.log 2>&1
