#!/usr/bin/env python
"""Objective share-of-voice counts (methodology §3.2d) — deterministic, symmetric, auditable.

For every brand in Gucci + pool.json competitor_set and every region block, the SAME query is sent to
Google News RSS in that block's editions (locale + language), restricted to the trailing 7 days:
    ("<English name>" OR "<local alias>") when:7d
Distinct editorial articles are counted per brand per block (deduped by normalised title across the
block's editions), with the outlets and two example links kept as evidence. Identical effort per
brand by construction: same query template, same editions, same page depth (one RSS page, max 100
items per edition). Replaces the LLM-run audit, whose search tool had no date filter.

Usage: python scripts/collect_sov.py [YYYY-MM-DD]  -> data/sov/<date>.json
"""
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import date, timedelta
from email.utils import parsedate_to_datetime
from html import unescape
from pathlib import Path

UA = {"User-Agent": "Mozilla/5.0 (gucci-intel sov scan)"}
# (gl, hl) editions per block; the alias language picks the local name for the query
EDITIONS = {
    "NEA": [("KR", "ko"), ("JP", "ja"), ("HK", "zh-HK")],
    "SEA": [("TH", "th"), ("SG", "en")],
    "NA": [("US", "en")],
    "EU": [("GB", "en"), ("FR", "fr"), ("IT", "it")],
}
SCRIPT = {  # which alias script belongs to which query language
    "ko": re.compile(r"[가-힣]"), "ja": re.compile(r"[぀-ヿ]"), "zh-HK": re.compile(r"[一-鿿]"),
    "th": re.compile(r"[฀-๿]"),
}
WINDOW_DAYS = 7
PAUSE = 0.8


def local_alias(aliases, hl):
    rx = SCRIPT.get(hl)
    if not rx:
        return None
    for a in aliases:
        if rx.search(a) and not (hl == "zh-HK" and SCRIPT["ja"].search(a)):
            return a
    return None


def norm_title(t):
    t = unicodedata.normalize("NFKC", t).lower()
    t = re.sub(r"\s*[-–—|]\s*[^-–—|]{2,40}$", "", t)   # strip trailing " - Outlet"
    return re.sub(r"[^\w가-힣぀-ヿ一-鿿฀-๿]+", " ", t).strip()


def rss(q, gl, hl):
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": q, "hl": hl, "gl": gl, "ceid": f"{gl}:{hl.split('-')[0]}"})
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30) as r:
        xml = r.read().decode("utf-8", "replace")
    out = []
    for it in xml.split("<item>")[1:]:
        title = unescape(re.search(r"<title>(.*?)</title>", it, re.S).group(1)) if "<title>" in it else ""
        link = re.search(r"<link>(.*?)</link>", it, re.S)
        pub = re.search(r"<pubDate>(.*?)</pubDate>", it)
        src = re.search(r'<source url="(.*?)">(.*?)</source>', it)
        try:
            day = parsedate_to_datetime(pub.group(1)).date() if pub else None
        except (TypeError, ValueError):
            day = None
        out.append({"title": title[:300], "day": day, "url": (link.group(1).strip() if link else ""),
                    "source": unescape(src.group(2)) if src else ""})
    return out


def run(date_str, root):
    root = Path(root)
    pool = json.load(open(root / "data" / "sources" / "pool.json", encoding="utf-8"))
    brands = ["Gucci"] + list(pool.get("competitor_set", []))
    aliases = pool.get("brand_aliases", {})
    end = date.fromisoformat(date_str)
    start = end - timedelta(days=WINDOW_DAYS - 1)
    regions, evidence, errors, queries = {}, {}, [], 0
    for region, eds in EDITIONS.items():
        regions[region], evidence[region] = {}, {}
        for brand in brands:
            seen, outlets, examples = {}, {}, []
            for gl, hl in eds:
                alias = local_alias(aliases.get(brand, []), hl)
                q = (f'("{brand}" OR "{alias}")' if alias else f'"{brand}"') + " when:7d"
                try:
                    items = rss(q, gl, hl)
                    queries += 1
                except Exception as e:  # noqa: BLE001
                    errors.append(f"{region}/{brand}/{gl}-{hl}: {e}")
                    continue
                for it in items:
                    if it["day"] is None or not (start <= it["day"] <= end):
                        continue
                    key = norm_title(it["title"])
                    if not key or key in seen:
                        continue
                    seen[key] = it
                    outlets[it["source"]] = outlets.get(it["source"], 0) + 1
                time.sleep(PAUSE)
            regions[region][brand] = len(seen)
            top = sorted(outlets.items(), key=lambda kv: -kv[1])[:6]
            examples = [{"title": it["title"], "url": it["url"]} for it in list(seen.values())[:2]]
            evidence[region][brand] = {"outlets": [o for o, _ in top], "examples": examples}
    doc = {
        "date": date_str,
        "method": "symmetric-gnews-rss-7d",
        "window": f"{start.isoformat()}~{date_str} (최근 7일)",
        "material": "Google News RSS에 색인된 편집 기사(뉴스·리뷰·피처); 권역별 로컬 에디션",
        "criteria": [
            f"브랜드 {len(brands)}곳(Gucci + pool.json competitor_set {len(brands) - 1}곳)에 동일한 질의 템플릿 (\"영문명\" OR \"현지어명\") when:7d 를 권역별 에디션마다 1회씩 실행",
            "권역 에디션: NEA=KR/ko·JP/ja·HK/zh, SEA=TH/th·SG/en, NA=US/en, EU=GB/en·FR/fr·IT/it; 동일 깊이(RSS 1페이지, 에디션당 최대 100건)",
            f"발행일이 {start.isoformat()}~{date_str} 안에 확인되는 기사만 집계; 권역 안에서 제목 정규화로 중복 제거",
            "스크립트 집계(scripts/collect_sov.py) — 브랜드별 탐색 깊이가 구조적으로 동일하며, 집계 매체와 예시 링크를 evidence에 남김",
        ],
        "criteria_en": [
            f"Same query template (\"English name\" OR \"local alias\") when:7d, once per brand per edition, for {len(brands)} brands (Gucci + {len(brands) - 1} competitor_set houses)",
            "Editions: NEA=KR/ko, JP/ja, HK/zh; SEA=TH/th, SG/en; NA=US/en; EU=GB/en, FR/fr, IT/it; identical depth (one RSS page, max 100 items per edition)",
            f"Only articles dated {start.isoformat()} to {date_str}; de-duplicated by normalised title within a block",
            "Script-counted (scripts/collect_sov.py): search depth is identical per brand by construction; outlets and two example links kept as evidence",
        ],
        "editions": EDITIONS, "queries": queries, "errors": errors,
        "regions": regions, "evidence": evidence,
    }
    out = root / "data" / "sov" / f"{date_str}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)
    for region, counts in regions.items():
        top = sorted(counts.items(), key=lambda kv: -kv[1])
        rank = 1 + sum(1 for b, c in counts.items() if c > counts.get("Gucci", 0))
        print(f"{region}: top {top[0][0]} {top[0][1]}, {top[1][0]} {top[1][1]} | Gucci {counts.get('Gucci')} (rank {rank}/{len(counts)})")
    print(f"sov: {out} queries={queries} errors={len(errors)}")
    return 0


def main():
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8")
    d = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    sys.exit(run(d, "."))


if __name__ == "__main__":
    main()
