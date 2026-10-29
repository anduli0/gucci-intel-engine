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

# Communities (free, no key): Reddit search RSS (descriptive UA, paced) and Lemmy.
REDDIT_UA = {"User-Agent": "gucci-intel-buzz/1.0 (research; by u/anduli0)"}
REDDIT_TERMS = ["gucci", "구찌", "グッチ", "古驰", "กุชชี่"]
REDDIT_PAUSE = 8.0
# Beta prior for splitting geo-unidentified posts between NA and EU: Reddit's
# desktop+mobile traffic is roughly US+CA ~55% vs Europe ~20% (public traffic
# estimates, 2025-26) -> NA share 0.73 within NA+EU, prior strength 10 posts.
PRIOR_NA, PRIOR_STRENGTH = 0.73, 10.0
GEO_SUBS = {
    "NEA": {"korea", "hanguk", "korean", "seoul", "japan", "japanlife", "tokyo", "china", "hongkong",
            "taiwan", "shanghai", "kpop", "kdrama"},
    "SEA": {"singapore", "thailand", "indonesia", "philippines", "malaysia", "vietnam", "bangkok",
            "manila", "jakarta", "kualalumpur"},
    "NA": {"canada", "toronto", "vancouver", "nyc", "newyorkcity", "losangeles", "chicago", "usa",
           "askanamerican", "boston", "sanfrancisco", "miami"},
    "EU": {"europe", "unitedkingdom", "casualuk", "uk", "london", "france", "paris", "italy", "milano",
           "germany", "de", "spain", "netherlands", "sweden", "ireland"},
}
SCRIPT_REGION = [(re.compile("[가-힣぀-ヿ一-鿿]"), "NEA"),
                 (re.compile("[฀-๿]"), "SEA")]


def community_scan(errors):
    """[(item, region or None)] from Reddit search RSS + Lemmy (last 7 days)."""
    out, seen = [], set()
    pat = re.compile("|".join(re.escape(x) for x in REDDIT_TERMS), re.I)
    for term in REDDIT_TERMS:
        url = "https://www.reddit.com/search.rss?" + urllib.parse.urlencode(
            {"q": term, "sort": "new", "t": "week", "limit": 100})
        xml = None
        for attempt in range(2):
            try:
                with urllib.request.urlopen(urllib.request.Request(url, headers=REDDIT_UA), timeout=30) as r:
                    xml = r.read().decode("utf-8", "replace")
                break
            except Exception as ex:  # noqa: BLE001
                if attempt == 1 or "429" not in str(ex):
                    errors.append(f"reddit {term}: {ex}")
                    break
                time.sleep(20)              # rate-limited: back off once
        if xml is None:
            time.sleep(REDDIT_PAUSE)
            continue
        for e in xml.split("<entry>")[1:]:
            link = re.search(r'<link href="(.*?)"', e)
            if not link or link.group(1) in seen:
                continue
            seen.add(link.group(1))
            title = unescape(re.search(r"<title>(.*?)</title>", e, re.S).group(1)) if "<title>" in e else ""
            sub = (re.search(r'<category term="(.*?)"', e) or [None, ""])[1].lower()
            day = (re.search(r"<updated>(.*?)</updated>", e) or [None, ""])[1][:10] or None
            region = next((r for r, subs in GEO_SUBS.items() if sub in subs), None)
            if region is None:
                region = next((r for rx, r in SCRIPT_REGION if rx.search(title)), None)
            out.append(({"source_type": "community", "source": f"Reddit r/{sub}", "url": link.group(1),
                         "title": title[:300], "published_at": day, "title_match": bool(pat.search(title))},
                        region))
        time.sleep(REDDIT_PAUSE)
    try:
        res = json.loads(urllib.request.urlopen(urllib.request.Request(
            "https://lemmy.world/api/v3/search?q=gucci&type_=Posts&sort=New&limit=50", headers=UA),
            timeout=30).read())
        for pv in res.get("posts", []):
            post = pv.get("post", {})
            title = post.get("name", "")
            out.append(({"source_type": "community", "source": "Lemmy", "url": post.get("ap_id"),
                         "title": title[:300], "published_at": (post.get("published") or "")[:10] or None,
                         "title_match": "gucci" in title.lower()},
                        next((r for rx, r in SCRIPT_REGION if rx.search(title)), None)))
    except Exception as ex:  # noqa: BLE001
        errors.append(f"lemmy: {ex}")
    return out


def allocate(scanned):
    """Region-identified posts go to their region (alloc 1). Unidentified posts
    (mostly English) are split between NA and EU by the posterior NA share: a
    Beta prior from Reddit traffic geography updated with the day's
    geo-identified NA vs EU posts (instead of a hard English->NA rule)."""
    n_na = sum(1 for _, r in scanned if r == "NA")
    n_eu = sum(1 for _, r in scanned if r == "EU")
    p_na = (n_na + PRIOR_NA * PRIOR_STRENGTH) / (n_na + n_eu + PRIOR_STRENGTH)
    by_region = {r: [] for r in GEO_SUBS}
    for it, r in scanned:
        if r:
            by_region[r].append({**it, "alloc": 1.0})
        else:
            by_region["NA"].append({**it, "alloc": round(p_na, 4)})
            by_region["EU"].append({**it, "alloc": round(1 - p_na, 4)})
    return by_region, {"NA_identified": n_na, "EU_identified": n_eu, "p_NA": round(p_na, 4)}


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
    comm_errors = []
    comm, alloc_info = allocate(community_scan(comm_errors))
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
               "domains_scanned": scanned, "community_allocation": alloc_info,
               "errors": errors + comm_errors, "items": list(items.values()) + comm[region]}
        (out_dir / f"{region}.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
        tm = sum(i["title_match"] for i in items.values())
        print(f"{region}: domains={scanned} news={len(items)} title_match={tm} "
              f"community={len(comm[region])} errors={len(errors) + len(comm_errors)}")
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
