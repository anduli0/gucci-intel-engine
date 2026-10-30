#!/usr/bin/env python
"""Turn the Gucci x Christmas edition on or off with one command.

    python scripts/xmas_toggle.py off     # back to the classic look (February)
    python scripts/xmas_toggle.py on      # bring the edition back (next December)
    python scripts/xmas_toggle.py status

What it flips (and nothing else):
  1. the switch in app/ui/index.html  -> window.GI_XMAS = {enabled: true|false, ...}
  2. the app icons app/ui/icon-{180,192,512}.png  <- app/ui/xmas/icons (on) | app/ui/icons-original (off)
  3. the SVG favicon data-URI in index.html        <- app/ui/xmas/icons/favicon-{xmas|classic}.txt
Everything else of the edition lives in app/ui/xmas/ (xmas.css, xmas.js) and is inert while off, so the
files stay in place for reuse. After flipping: commit, push, and run publish-only (or wait for the daily run).
"""
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
UI = ROOT / "app" / "ui"
HTML = UI / "index.html"
ICONS = ("icon-180.png", "icon-192.png", "icon-512.png")


def status(t):
    m = re.search(r"window\.GI_XMAS = \{enabled: (true|false)", t)
    return m.group(1) if m else "missing"


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "status"
    t = HTML.read_text(encoding="utf-8")
    if mode == "status":
        print("christmas edition:", status(t))
        return 0
    if mode not in ("on", "off"):
        print(__doc__)
        return 2
    on = mode == "on"
    t2, n = re.subn(r"window\.GI_XMAS = \{enabled: (true|false)", f"window.GI_XMAS = {{enabled: {'true' if on else 'false'}", t)
    if n != 1:
        print("switch not found in index.html")
        return 1
    fav = (UI / "xmas" / "icons" / ("favicon-xmas.txt" if on else "favicon-classic.txt")).read_text(encoding="utf-8").strip()
    t2, n = re.subn(r'(<link rel="icon" href=")data:image/svg\+xml,[^"]*(">)', lambda m: m.group(1) + fav + m.group(2), t2)
    if n != 1:
        print("favicon link not found")
        return 1
    src = UI / "xmas" / "icons" if on else UI / "icons-original"
    for name in ICONS:
        shutil.copy2(src / name, UI / name)
    HTML.write_text(t2, encoding="utf-8")
    print(f"christmas edition: {'on' if on else 'off'} (switch, favicon, {len(ICONS)} icons). Next: git commit, push, publish-only.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
