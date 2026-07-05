#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Export a static snapshot of the Gucci Intelligence viewer.

Pulls every read API from the running local server (port 8790) and writes a
fully static site into C:\\Users\\andul\\gucci-intel-site — deployable to any
static host (GitHub Pages). The UI's relative fetches and client-side language
split make the same index.html work unchanged.
"""
import json
import shutil
import sys
import urllib.parse
import urllib.request
from pathlib import Path

import os

BASE = os.environ.get("EXPORT_BASE", "http://127.0.0.1:8790")
ROOT = Path(__file__).resolve().parent.parent
OUT = Path(os.environ.get("EXPORT_OUT", r"C:\Users\andul\gucci-intel-site"))

ENDPOINTS = ["summary", "timeseries", "reports", "sov", "luxury", "events",
             "pool", "news", "calendar", "ambassadors", "products"]


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return r.read()


def main():
    (OUT / "api" / "report").mkdir(parents=True, exist_ok=True)
    (OUT / "product-images").mkdir(parents=True, exist_ok=True)

    # 1. JSON APIs (extensionless files; fetch().json() ignores content-type)
    for ep in ENDPOINTS:
        (OUT / "api" / ep).write_bytes(get(f"/api/{ep}"))

    # 2. Static stubs: viewer mode, no runner
    # "static": true tells the UI to switch run control to the remote engine
    (OUT / "api" / "status").write_text(json.dumps({
        "static": True, "readonly": True, "running": False, "cmd": None, "arg": "",
        "started": None, "exit": None, "log": None, "auth_error": False,
        "claude_available": False, "ui_mtime": 0, "root": ""}), encoding="utf-8")
    (OUT / "api" / "runlog").write_text('{"lines": []}', encoding="utf-8")

    # 3. Full report files (client splits KO/EN)
    reports = json.loads(get("/api/reports"))["reports"]
    for r in reports:
        rel = r["path"]
        dest = OUT / "api" / "report" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(get("/api/report/" + urllib.parse.quote(rel, safe="/")))

    # 4. UI shell + icons + manifest
    ui = ROOT / "app" / "ui"
    shutil.copy2(ui / "index.html", OUT / "index.html")
    for name in ("icon-180.png", "icon-192.png", "icon-512.png", "manifest.webmanifest"):
        shutil.copy2(ui / name, OUT / name)

    # 5. Product images
    img_src = ROOT / "data" / "products" / "images"
    if img_src.exists():
        for p in img_src.iterdir():
            if p.is_file():
                shutil.copy2(p, OUT / "product-images" / p.name)

    # 6. Hosting hygiene: no search indexing, no jekyll processing
    (OUT / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")
    (OUT / ".nojekyll").write_text("", encoding="utf-8")

    n_imgs = len(list((OUT / "product-images").iterdir()))
    print(f"static export OK: {OUT} | api {len(ENDPOINTS)+2}, reports {len(reports)}, images {n_imgs}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
