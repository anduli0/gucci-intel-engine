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
    except Exception as e:  # 403/timeout pages are cached as none too; delete the cache entry to retry
        print(f"  skip {url[:80]} ({type(e).__name__})")
        cache[url] = None
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


def add_figures(text, cache, taken=frozenset()):
    """taken = images already used by OTHER reports: a photo appears on the site once.
    Within this edition no repeats either; a section whose only candidate is already
    used gets no figure at all (omit rather than repeat)."""
    lines, seen, n = [], set(), 0
    for ln in text.split("\n"):
        m = re.match(r"^!\[[^\]]*\]\((\S+)", ln)
        if m:
            if m.group(1) in seen or m.group(1) in taken:
                n -= 1
                continue
            seen.add(m.group(1))
        lines.append(ln)
    srcs = sources(lines)
    if not srcs:
        return "\n".join(lines), n
    out, i, used = [], 0, set()
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
                        if img and img not in seen and img not in taken:
                            seen.add(img)
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
    total, taken = 0, set()  # evergreen CD dossiers first, so they keep their photos
    for d in DIRS:
        for p in sorted((ROOT / "data" / "reports" / d).glob("*.md")):
            text = p.read_text(encoding="utf-8")
            if p.name.endswith("-index-interpretation.md"):  # the index report stays plain: no photos
                clean = re.sub(r"^!\[[^\]]*\]\(\S+[^\n]*\n\n?", "", text, flags=re.M)
                if clean != text and not dry:
                    p.write_text(clean, encoding="utf-8")
                    print(f"{p.relative_to(ROOT)}: photos removed")
                continue
            halves = text.split(MARK)
            done = [add_figures(h, cache, taken) for h in halves]
            for t, _ in done:
                taken.update(re.findall(r"^!\[[^\]]*\]\((\S+)", t, re.M))
            n = sum(c for _, c in done)
            if n or MARK.join(t for t, _ in done) != text:
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
    _d = _r + "\n## 2. B\n\nz [2] w\n\n## 출처\n\n[2] Pub — d2 — https://example.invalid/b\n"
    _r2, _n2 = add_figures(_d, {"https://example.invalid/a": "https://img/x.jpg", "https://example.invalid/b": "https://img/x.jpg"})
    assert _n2 == 0 and _r2.count("![") == 1, _r2  # same image again -> omitted
    assert add_figures(_t, {"https://example.invalid/a": "https://img/x.jpg"}, {"https://img/x.jpg"})[0].count("![") == 0  # used elsewhere -> omitted
    main()
