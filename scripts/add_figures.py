#!/usr/bin/env python3
"""Put photographs into the published reports (magazine layout).

For every report under data/reports/{cd,daily,weekly,special,events}, each numbered
section (and the 핵심 요약 / Key Summary) gets ONE figure: the og:image of the first
source [n] that section cites, with the 출처 description as caption and the
publisher|article as credit. Hotlink only (never rehosted). Idempotent: a section
that already carries a `![` figure is left alone, so analyst-chosen figures win.
Cache: data/figures/og-cache.json (url -> image or null when the page has none).

Usage: python scripts/add_figures.py [--dry]
"""
import html
import json
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIRS = ["cd", "daily", "weekly", "special", "events"]
CACHE = ROOT / "data" / "figures" / "og-cache.json"
MARK = "<!-- ===== ENGLISH EDITION ===== -->"
SRC_RE = re.compile(r"^\[(\d+)\]\s+(.+?)\s+[—–-]+\s+(.+?)\s+[—–-]+\s+(https?://\S+)\s*$")
SEC_RE = re.compile(r"^## (?:\d+\.|핵심 요약|Key Summary)")
META_RE = re.compile(r'<meta\s[^>]*?(?:property|name)=["\'](?:og:image|og:image:url|og:image:secure_url|twitter:image)["\'][^>]*?content=["\']([^"\']+)', re.I)
META_RE2 = re.compile(r'<meta\s[^>]*?content=["\']([^"\']+)["\'][^>]*?(?:property|name)=["\'](?:og:image|og:image:url|og:image:secure_url|twitter:image)["\']', re.I)
BAD = ("logo", "placeholder", "default", "favicon", "avatar", "icon")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"


def og_image(url, cache):
    if url in cache:
        return cache[url]
    try:
        req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,*/*"})
        with urllib.request.urlopen(req, timeout=12) as r:
            head = r.read(600_000).decode("utf-8", "ignore")
    except Exception as e:  # fetch failure is not cached: retried next run
        print(f"  skip {url[:80]} ({type(e).__name__})")
        return None
    img = None
    m = META_RE.search(head) or META_RE2.search(head)
    if m:
        cand = html.unescape(m.group(1)).strip().replace(" ", "%20")
        if cand.startswith("http") and not any(b in cand.lower() for b in BAD):
            img = cand
    cache[url] = img
    return img


def sources(lines):
    out = {}
    for ln in lines:
        m = SRC_RE.match(ln.strip())
        if m:
            out[m.group(1)] = (m.group(2).strip(), m.group(3).strip(), m.group(4).rstrip(").,"))
    return out


def add_figures(text, cache):
    lines = text.split("\n")
    srcs = sources(lines)
    if not srcs:
        return text, 0
    out, i, n, used = [], 0, 0, set()
    while i < len(lines):
        if not SEC_RE.match(lines[i]):
            out.append(lines[i])
            i += 1
            continue
        j = i + 1
        while j < len(lines) and not lines[j].startswith("## "):
            j += 1
        body = lines[i:j]
        if not any(b.startswith("![") for b in body):
            fig = None
            for k, b in enumerate(body[1:], 1):
                for num in re.findall(r"\[(\d+)\]", b):
                    if num in srcs and num not in used:
                        pub, desc, url = srcs[num]
                        img = og_image(url, cache)
                        if img:
                            fig = (k, num, pub, desc, url, img)
                            break
                if fig:
                    break
            if fig:
                k, num, pub, desc, url, img = fig
                used.add(num)
                cap = re.sub(r"[\[\]\"]", "", desc)
                pub = pub.replace('"', "").replace("|", "/")
                body = body[: k + 1] + ["", f'![{cap}]({img} "{pub}|{url}")'] + body[k + 1 :]
                n += 1
        out.extend(body)
        i = j
    return "\n".join(out), n


def main():
    dry = "--dry" in sys.argv
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    total = 0
    for d in DIRS:
        for p in sorted((ROOT / "data" / "reports" / d).glob("*.md")):
            text = p.read_text(encoding="utf-8")
            halves = text.split(MARK)
            done = [add_figures(h, cache) for h in halves]
            n = sum(c for _, c in done)
            if n:
                total += n
                print(f"{p.relative_to(ROOT)}: +{n} figures")
                if not dry:
                    p.write_text(MARK.join(t for t, _ in done), encoding="utf-8")
    if not dry:
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"figures added: {total}")


if __name__ == "__main__":
    # self-check of the section/figure insertion on a tiny synthetic report
    _t = "## 1. A\n\nx [1] y\n\n## 출처\n\n[1] Pub — desc — https://example.invalid/a\n"
    _r, _n = add_figures(_t, {"https://example.invalid/a": "https://img/x.jpg"})
    assert _n == 1 and '![desc](https://img/x.jpg "Pub|https://example.invalid/a")' in _r, _r
    assert add_figures(_r, {"https://example.invalid/a": "https://img/x.jpg"})[1] == 0
    main()
