#!/usr/bin/env python3
"""Put photographs into the published reports (balanced fashion-analyst layout).

For every report under data/reports/{cd,daily,weekly,special,events} (NOT the
index-interpretation report, which stays plain), each numbered section (and the
핵심 요약 / Key Summary) gets ONE figure: the og:image of the first source [n] that
section cites, with the 출처 description as caption and publisher|article as credit.
Hotlink only (never rehosted). Idempotent: a section that already carries a `![`
figure is left alone, so analyst-chosen figures win.

Duplicate rules
- Within one report: ABSOLUTE. The same photo (also another crop/size of it, detected
  by normalized cross-correlation on 80px thumbnails) appears once; a section whose
  only candidate is already used gets no figure.
- Across reports: avoided. A photo already used by another report (exact URL or
  near-identical average hash) is not reused.

Caches: data/figures/og-cache.json (article -> image url | null), img-hash.json
(image -> hash | null), thumbs/ (80px grayscale PNG per image). Delete an entry to retry.
Usage: python scripts/add_figures.py [--dry]
"""
import hashlib
import html
import io
import json
import pathlib
import re
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
DIRS = ["cd", "daily", "weekly", "special", "events"]
FIG = ROOT / "data" / "figures"
CACHE, HASHES, THUMBS = FIG / "og-cache.json", FIG / "img-hash.json", FIG / "thumbs"
MARK = "<!-- ===== ENGLISH EDITION ===== -->"
SRC_RE = re.compile(r"^\[(\d+)\]\s+(.+?)\s+[—–-]+\s+(.+?)\s+[—–-]+\s+(https?://\S+)\s*$")
SEC_RE = re.compile(r"^## (?:\d+\.|핵심 요약|Key Summary)")
FIG_RE = re.compile(r"^!\[[^\]]*\]\((\S+)", re.M)
META_RE = re.compile(r'<meta\s[^>]*?(?:property|name)=["\'](?:og:image|og:image:url|og:image:secure_url|twitter:image)["\'][^>]*?content=["\']([^"\']+)', re.I)
META_RE2 = re.compile(r'<meta\s[^>]*?content=["\']([^"\']+)["\'][^>]*?(?:property|name)=["\'](?:og:image|og:image:url|og:image:secure_url|twitter:image)["\']', re.I)
# generic / stock / logo images are not photos of the story
BAD = ("logo", "placeholder", "default", "favicon", "avatar", "icon", "pexels", "unsplash", "stock-photo", "ad-hoc-news.de", "marketbeat.com")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36"
SAME = 0.85  # NCC above this = same photo


def fetch(url, limit):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html,image/*,*/*"})
    with urllib.request.urlopen(req, timeout=12) as r:
        return r.read(limit)


def _og(url):
    m = None
    try:
        head = fetch(url, 600_000).decode("utf-8", "ignore")
        m = META_RE.search(head) or META_RE2.search(head)
    except Exception as e:  # cached as none too; delete the cache entry to retry
        print(f"  skip {url[:80]} ({type(e).__name__})")
    if not m:
        return None
    cand = html.unescape(m.group(1)).strip().replace(" ", "%20")
    # WordPress og:images are often hard-cropped (?w=..&h=..&crop=1): ask for the uncropped width instead
    if "wp-content/uploads" in cand and "crop=" in cand:
        cand = cand.split("?")[0] + "?w=1200"
    return cand if cand.startswith("http") else None


def site_default(url, cache):
    """The homepage og:image of the article's host: the logo card a site returns for every article."""
    host = url.split("/")[2]
    key = "home:" + host
    if key not in cache:
        cache[key] = _og(f"https://{host}/")
    return cache[key]


def og_image(url, cache):
    if url in cache:
        return cache[url]
    img = _og(url)
    home = img and site_default(url, cache)
    if img and (any(b in img.lower() for b in BAD) or (home and (img == home or same_photo(thumb(img), thumb(home))))):
        img = None
    cache[url] = img
    return img


def thumb(url):
    """80px grayscale thumbnail as a numpy array (cached on disk), or None."""
    import numpy as np
    from PIL import Image
    p = THUMBS / (hashlib.sha1(url.encode()).hexdigest() + ".png")
    try:
        if p.exists():
            return np.asarray(Image.open(p), dtype=np.float32)
        im = Image.open(io.BytesIO(fetch(url, 3_000_000))).convert("L")
        im.thumbnail((80, 80))
        im.save(p)
        return np.asarray(im, dtype=np.float32)
    except Exception as e:
        print(f"  nothumb {url[:70]} ({type(e).__name__})")
        return None


def ahash(a):
    if a is None:
        return None
    from PIL import Image
    im = Image.fromarray(a.astype("uint8")).resize((8, 8))
    px = list(im.getdata())
    avg = sum(px) / 64
    return "%016x" % int("".join("1" if v > avg else "0" for v in px), 2)


def contains(big, small):
    """max NCC of `small` (rescaled) slid over `big`."""
    import numpy as np
    from PIL import Image
    best, (H, W) = 0.0, big.shape
    for s in (1.0, 0.85, 0.7, 0.6, 0.5, 0.42, 0.35):
        h, w = int(small.shape[0] * s), int(small.shape[1] * s)
        if h < 12 or w < 12 or h > H or w > W:
            continue
        sm = np.asarray(Image.fromarray(small.astype("uint8")).resize((w, h)), dtype=np.float32)
        sm = sm - sm.mean()
        sn = np.sqrt((sm * sm).sum()) + 1e-6
        for y in range(0, H - h + 1, 2):
            for x in range(0, W - w + 1, 2):
                win = big[y:y + h, x:x + w]
                wm = win - win.mean()
                best = max(best, float((wm * sm).sum() / ((np.sqrt((wm * wm).sum()) + 1e-6) * sn)))
    return best


def same_photo(a, b):
    return a is not None and b is not None and max(contains(a, b), contains(b, a)) >= SAME


def bigrams(cap):
    t = re.sub(r"[^0-9a-zA-Z가-힣]", "", cap.lower())
    return {t[i:i + 2] for i in range(len(t) - 1)}


def same_subject(cap, caps, ignore=frozenset()):
    """Caption overlap (character-bigram Jaccard) high enough to be the same person/story.
    `ignore` = bigrams of the report title, so a dossier's own subject does not count."""
    a = bigrams(cap) - ignore
    for c in caps:
        b = bigrams(c) - ignore
        if len(a & b) / max(1, len(a | b)) >= 0.3:
            return True
    return False


def near_hash(h, pool):
    if not h:
        return False
    v = int(h, 16)
    return any(bin(v ^ int(q, 16)).count("1") <= 6 for q in pool if q)


class Dedupe:
    """Within-report (NCC, absolute) and across-report (hash, avoided) duplicate checks."""

    def __init__(self, hashes, site_defaults=None):
        self.hashes = hashes
        self.site_defaults = site_defaults or {}
        self.taken_urls, self.taken_hashes = set(), set()

    def h(self, url):
        if url not in self.hashes:
            self.hashes[url] = ahash(thumb(url))
        return self.hashes[url]

    def used_elsewhere(self, url):
        return url in self.taken_urls or near_hash(self.h(url), self.taken_hashes)

    def dup_in_edition(self, url, cap, kept, title=""):
        """kept = [(url, caption)] already in this edition."""
        if any(url == u for u, _ in kept) or same_subject(cap, [c for _, c in kept], bigrams(title)):
            return True
        t = thumb(url)
        return any(same_photo(t, thumb(u)) for u, _ in kept)

    def commit(self, urls):
        for u in urls:
            self.taken_urls.add(u)
            self.taken_hashes.add(self.h(u))


def sources(lines):
    out = {}
    for ln in lines:
        m = SRC_RE.match(ln.strip())
        if m:
            out[m.group(1)] = (m.group(2).strip(), m.group(3).strip(), m.group(4).rstrip(").,"))
    return out


def add_figures(text, cache, dd):
    lines, kept, n = [], [], 0
    title = next((l[2:] for l in text.split("\n") if l.startswith("# ")), "")
    for ln in text.split("\n"):
        m = FIG_RE.match(ln)
        if m:
            u, cap = m.group(1), m.group(0)[2:m.group(0).index("](")]
            if any(b in u.lower() for b in BAD) or u in {v for k, v in dd.site_defaults.items() if v}:  # generic/stock/logo card
                n -= 1
                continue
            if "wp-content/uploads" in u and "crop=" in u:  # un-crop (same rule as og_image)
                u2 = u.split("?")[0] + "?w=1200"
                ln, u = ln.replace(u, u2), u2
            if dd.dup_in_edition(u, cap, kept, title) or dd.used_elsewhere(u):
                n -= 1
                continue
            kept.append((u, cap))
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
                        cap = re.sub(r"[\[\]\"]", "", desc)
                        if img and not dd.used_elsewhere(img) and not dd.dup_in_edition(img, cap, kept, title):
                            kept.append((img, cap))
                            fig = (k, num, pub, desc, url, img)
                            break
                if fig:
                    break
            if fig:
                k, num, pub, desc, url, img = fig
                used.add(num)
                pub = pub.replace('"', "").replace("|", "/")
                body = body[: k + 1] + ["", f'![{cap}]({img} "{pub}|{url}")'] + body[k + 1 :]
                n += 1
        out.extend(body)
        i = j
    return "\n".join(out), n


def main():
    dry = "--dry" in sys.argv
    THUMBS.mkdir(parents=True, exist_ok=True)
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    for k, v in list(cache.items()):  # apply the BAD / un-crop rules to images cached by earlier runs
        if v and any(b in v.lower() for b in BAD):
            cache[k] = None
        elif v and "wp-content/uploads" in v and "crop=" in v:
            cache[k] = v.split("?")[0] + "?w=1200"
    for k, v in list(cache.items()):  # re-check cached article images against their site's logo card
        if v and not k.startswith("home:") and v == site_default(k, cache):
            cache[k] = None
    dd = Dedupe(json.loads(HASHES.read_text(encoding="utf-8")) if HASHES.exists() else {},
                {k: v for k, v in cache.items() if k.startswith("home:")})
    total = 0
    for d in DIRS:  # evergreen CD dossiers first, so they keep their photos
        for p in sorted((ROOT / "data" / "reports" / d).glob("*.md")):
            text = p.read_text(encoding="utf-8")
            if p.name.endswith("-index-interpretation.md"):  # the index report stays plain: no photos
                clean = re.sub(r"^!\[[^\]]*\]\(\S+[^\n]*\n\n?", "", text, flags=re.M)
                if clean != text and not dry:
                    p.write_text(clean, encoding="utf-8")
                    print(f"{p.relative_to(ROOT)}: photos removed")
                continue
            done = [add_figures(h, cache, dd) for h in text.split(MARK)]
            new = MARK.join(t for t, _ in done)
            dd.commit(u for t, _ in done for u in FIG_RE.findall(t))
            n = sum(c for _, c in done)
            if new != text:
                total += n
                print(f"{p.relative_to(ROOT)}: {n:+d} figures")
                if not dry:
                    p.write_text(new, encoding="utf-8")
    if not dry:
        CACHE.write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")
        HASHES.write_text(json.dumps(dd.hashes, ensure_ascii=False, indent=0), encoding="utf-8")
    print(f"figures net: {total:+d}")


if __name__ == "__main__":
    # self-check on a synthetic report: insert once, idempotent, omit when the photo is already used
    class _DD(Dedupe):
        def __init__(self):
            super().__init__({})

        def dup_in_edition(self, url, cap, kept, title=""):
            return any(url == u for u, _ in kept)

        def h(self, url):
            return None

    _dd = _DD()
    _t = "## 1. A\n\nx [1] y\n\n## 출처\n\n[1] Pub — desc — https://example.invalid/a\n"
    _c = {"https://example.invalid/a": "https://img/x.jpg", "https://example.invalid/b": "https://img/x.jpg"}
    _r, _n = add_figures(_t, _c, _dd)
    assert _n == 1 and '![desc](https://img/x.jpg "Pub|https://example.invalid/a")' in _r, _r
    assert add_figures(_r, _c, _dd)[1] == 0
    _d = _r + "\n## 2. B\n\nz [2] w\n\n## 출처\n\n[2] Pub — d2 — https://example.invalid/b\n"
    assert add_figures(_d, _c, _dd)[0].count("![") == 1  # same image again -> omitted
    assert same_subject("머라이어 캐리의 '버터플라이' 캡슐 공개, 구찌 홀리데이 캠페인", ["머라이어 캐리가 전면에 선 구찌 2026 홀리데이 캠페인"])
    assert not same_subject("세금 추징에 루이비통·구찌 사던 중국 부자들의 이탈", ["머라이어 캐리가 전면에 선 구찌 2026 홀리데이 캠페인"])
    assert not same_subject("조너선 앤더슨 디올 SS26 여성 데뷔 리뷰", ["조너선 앤더슨 디올 AW26 남성 데뷔 쇼 리뷰, 폴 푸아레"], bigrams("조너선 앤더슨 — Dior"))
    _dd.taken_urls.add("https://img/x.jpg")
    assert add_figures(_t, _c, _dd)[0].count("![") == 0  # used by another report -> omitted
    main()
