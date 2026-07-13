#!/usr/bin/env python
"""Special/Event desk cadence guard, shared by daily-update.bat and cloud-daily.sh.

Exit 0 = fresh (a deep-dive published in the last 3 days) -> skip.
Exit 1 = stale (>=3 days, or none) -> caller runs `/gucci-special auto`.

Age is derived from the CONTENT date (filename prefix, then a meta-line date in
the first 600 chars), NOT os.path.getmtime: every daily run's git checkout,
publish and retention steps reset file mtimes to ~now, so an mtime-based age is
always ~0 and the guard would never fire.
"""
import glob
import re
import sys
from datetime import date, datetime

DATE_ANY = re.compile(r"\d{4}-\d{2}-\d{2}")


def rdate(f):
    m = DATE_ANY.search(f.rsplit("/", 1)[-1].rsplit("\\", 1)[-1])
    if m:
        return m.group(0)
    try:
        with open(f, encoding="utf-8") as fh:
            m = DATE_ANY.search(fh.read(600))
        return m.group(0) if m else None
    except OSError:
        return None


fs = glob.glob("data/reports/special/*.md") + glob.glob("data/reports/events/*.md")
dates = [d for d in (rdate(f) for f in fs) if d]
if not dates:
    age = 999
else:
    newest = max(datetime.strptime(d, "%Y-%m-%d").date() for d in dates)
    age = (date.today() - newest).days

print("special desk age(days): %d" % age)
sys.exit(0 if age < 3 else 1)
