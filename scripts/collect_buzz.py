"""Large-scale Buzz volume scan (gmai-formula.md §3.2b v2.4).

The regional collectors read ~10-15 items per region per day, so Buzz volume
rested on a thin, LLM-chosen sample. This script scans EVERY news source in
data/sources/buzz_registry.json (global + regional) through Google News RSS
(free, no key): one site-scoped query per source domain for the last 7 days.
Items feed Buzz volume ONLY (never Sentiment/Engagement/SOV); compute_gmai
weights them by source influence, recency and title relevance.

Output: data/buzz/{DATE}/{REGION}.json. Fail-soft: errors are recorded and the
script always exits 0.

Usage: python scripts/collect_buzz.py [YYYY-MM-DD] [--root ROOT]
"""
import argparse
import json
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 (gucci-intel buzz scan)"}
TERMS = {
    "NEA": ["gucci", "구찌", "グッチ", "古驰", "古馳"],
    "SEA": ["gucci", "กุชชี่"],
    "NA": ["gucci"],
    "EU": ["gucci"],
}
DEFAULT_EDITION = {"NEA": ("KR", "ko"), "SEA": ("SG", "en"), "NA": ("US", "en"), "EU": ("GB", "en")}
TLD_EDITION = {".kr": ("KR", "ko"), ".jp": ("JP", "ja"), ".cn": ("HK", "zh-Hant"), ".fr": ("FR", "fr"),
               ".it": ("IT", "it"), ".de": ("DE", "de"), ".es": ("ES", "es"), ".th": ("TH", "th"),
               ".id": ("ID", "id"), ".my": ("MY", "en"), ".sg": ("SG", "en"), ".vn": ("VN", "vi"),
               ".uk": ("GB", "en")}
PAUSE = 0.6  # seconds between requests


def edition(domain, region):
    for tld, ed in TLD_EDITION.items():
        if domain.endswith(tld):
            return ed
    return DEFAULT_EDITION[region]


def scan(domain, region):
    gl, hl = edition(domain, region)
    q = "(" + " OR ".join(TERMS[region]) + f") site:{domain} when:7d"
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": q, "hl": hl, "gl": gl, "ceid": f"{gl}:{hl.split('-')[0]}"})
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        xml = r.read().decode("utf-8", "replace")
    out = []
    pat = re.compile("|".join(re.escape(t) for t in TERMS[region]), re.I)
    for it in xml.split("<item>")[1:]:
        title = unescape(re.search(r"<title>(.*?)</title>", it, re.S).group(1)) if "<title>" in it else ""
        pub = re.search(r"<pubDate>(.*?)</pubDate>", it)
        src = re.search(r'<source url="(.*?)">(.*?)</source>', it)
        try:
            day = parsedate_to_datetime(pub.group(1)).date().isoformat() if pub else None
        except (TypeError, ValueError):
            day = None
        out.append({
            "source_type": "news", "published_at": day,
            "title": title[:300],
            "url": src.group(1) if src else f"https://{domain}",
            "source": unescape(src.group(2)) if src else domain,
            "title_match": bool(pat.search(title)),
        })
    return out


def run(date_str, root):
    reg_path = Path(root) / "data" / "sources" / "buzz_registry.json"
    reg = json.loads(reg_path.read_text(encoding="utf-8"))
    out_dir = Path(root) / "data" / "buzz" / date_str
    out_dir.mkdir(parents=True, exist_ok=True)
    for region, sources in reg["regions"].items():
        items, errors, scanned = {}, [], 0
        for e in reg["global"] + sources:
            if e["channel"] != "news":
                continue
            for domain in e["domains"]:
                scanned += 1
                try:
                    for it in scan(domain, region):
                        items[(it["title"], it["source"])] = it
                except Exception as ex:  # noqa: BLE001 - fail-soft by design
                    errors.append(f"{domain}: {ex}")
                time.sleep(PAUSE)
        doc = {"date": date_str, "region": region,
               "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "domains_scanned": scanned, "errors": errors, "items": list(items.values())}
        (out_dir / f"{region}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        tm = sum(i["title_match"] for i in items.values())
        print(f"{region}: domains={scanned} items={len(items)} title_match={tm} errors={len(errors)}")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("date", nargs="?", default=date.today().isoformat())
    ap.add_argument("--root", default=str(Path(__file__).resolve().parent.parent))
    a = ap.parse_args()
    try:
        return run(a.date, a.root)
    except Exception as e:  # noqa: BLE001 - never break the pipeline
        print(f"WARN: buzz scan failed: {e}", file=sys.stderr)
        return 0


if __name__ == "__main__":
    sys.exit(main())
