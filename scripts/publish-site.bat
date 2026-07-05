@echo off
rem Export a fresh static snapshot into this repo's /docs and push —
rem GitHub Pages serves gucci-intel-engine:/docs.
cd /d C:\Users\andul\gucci-intel
set "EXPORT_OUT=C:\Users\andul\gucci-intel\docs"
python scripts\export_static.py >> logs\publish-site.log 2>&1
git -c user.name="anduli0" -c user.email="minkyu494@gmail.com" pull --rebase origin main >> logs\publish-site.log 2>&1
git add docs data >> logs\publish-site.log 2>&1
git -c user.name="anduli0" -c user.email="minkyu494@gmail.com" commit -m "local publish %date% %time%" >> logs\publish-site.log 2>&1
git push >> logs\publish-site.log 2>&1
