#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Retention policy: keep ~2 weeks of dated artifacts, delete oldest beyond.

Safety rules baked in:
- The GMAI time series CSV and 30-day baseline are NEVER touched (chart history).
- For single-snapshot kinds (calendar/ambassadors/products/news/sov/index
  snapshots) the newest file is ALWAYS kept, even if older than the window.
- For each report category the newest report is always kept.
- Product images not referenced by the latest product board are removed.
"""
import json
import re
import shutil
import sys
from datetime import date, timedelta
from pathlib import Path

KEEP_DAYS = 14
ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DATE_RE = re.compile(r"(\d{4}-\d{2}-\d{2})")
CUTOFF = (date.today() - timedelta(days=KEEP_DAYS)).isoformat()
removed = []


def file_date(p: Path):
    m = DATE_RE.search(p.name)
    if m:
        return m.group(1)
    return date.fromtimestamp(p.stat().st_mtime).isoformat()


def clean_dated_dirs(base: Path):
    """Directories named YYYY-MM-DD (raw / sentiment / luxury / events by mtime)."""
    if not base.exists():
        return
    for d in sorted(p for p in base.iterdir() if p.is_dir()):
        if file_date(d) < CUTOFF:
            shutil.rmtree(d, ignore_errors=True)
            removed.append(str(d.relative_to(ROOT)))


def clean_dated_files(base: Path, pattern: str):
    """Dated files; the newest one always survives."""
    if not base.exists():
        return
    files = sorted(base.glob(pattern), key=file_date)
    for p in files[:-1]:  # newest always kept
        if file_date(p) < CUTOFF:
            p.unlink(missing_ok=True)
            removed.append(str(p.relative_to(ROOT)))


def main():
    for kind in ("raw", "sentiment", "luxury"):
        clean_dated_dirs(DATA / kind)
    clean_dated_dirs(DATA / "events")  # per-event dirs, mtime-based

    clean_dated_files(DATA / "news", "*.json")
    clean_dated_files(DATA / "news", "*-digest.md")
    clean_dated_files(DATA / "sov", "*.json")
    clean_dated_files(DATA / "calendar", "*.json")
    clean_dated_files(DATA / "ambassadors", "*.json")
    clean_dated_files(DATA / "products", "*.json")
    # index snapshots only — gmai_timeseries.csv / baseline_30d.json are permanent
    if (DATA / "index").exists():
        snaps = sorted((p for p in (DATA / "index").glob("*.json")
                        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", p.stem)), key=file_date)
        for p in snaps[:-1]:
            if file_date(p) < CUTOFF:
                p.unlink(missing_ok=True)
                removed.append(str(p.relative_to(ROOT)))

    for cat in ("daily", "weekly", "events", "special"):
        clean_dated_files(DATA / "reports" / cat, "*.md")

    clean_dated_files(DATA / "analysis", "*.md")

    # product images: drop files the latest board no longer references
    img_dir = DATA / "products" / "images"
    boards = sorted((DATA / "products").glob("*.json"), key=file_date)
    if img_dir.exists() and boards:
        latest = json.loads(boards[-1].read_text(encoding="utf-8"))
        keep = {it.get("image_local") for c in latest.get("categories", [])
                for it in c.get("items", []) if it.get("image_local")}
        for p in img_dir.iterdir():
            if p.is_file() and p.name not in keep and file_date(p) < CUTOFF:
                p.unlink(missing_ok=True)
                removed.append(str(p.relative_to(ROOT)))

    # pipeline logs
    logs = ROOT / "logs"
    for pat in ("apprun-*.log", "schtask-*.log"):
        for p in logs.glob(pat):
            if file_date(p) < CUTOFF:
                p.unlink(missing_ok=True)
                removed.append(str(p.relative_to(ROOT)))

    print(f"retention cleanup: removed {len(removed)} item(s), window {KEEP_DAYS}d (cutoff {CUTOFF})")
    for r in removed[:30]:
        print("  -", r)
    return 0


if __name__ == "__main__":
    sys.exit(main())
