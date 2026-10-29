"""Empirical test of YouTube region-assignment rules for the Engagement / Buzz
collectors (gmai-formula.md §3.2c). Ground truth = uploader channel country
(channels.list snippet.country), available for a subset of channels.

Rules compared (same 7-day window, same queries as collect_engagement.py):
  A  search regionCode only
  B  regionCode + relevanceLanguage            (production rule until now)
  D  B, then reassign every video whose channel country is known to the
     region of that country; unknown-country videos keep their B region
Metrics per rule: n per region, known-country share, precision (assigned
region == true region among known), cross-region duplication, chi-square test
of independence assigned x true region with Cramér's V. D's precision on
unknown-country videos is estimated with B's precision (missing-at-random).

Needs YOUTUBE_API_KEY. Writes data/analysis/region-assignment-{DATE}.json.
Usage: python scripts/analyze_region_assignment.py [YYYY-MM-DD]
"""
import json
import os
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

from scipy.stats import chi2_contingency

sys.path.insert(0, str(Path(__file__).resolve().parent))
from collect_engagement import WINDOW_DAYS, YT_API, YT_CHANNEL, YT_REGION_QUERIES  # noqa: E402

COUNTRY_REGION = {}
for r, cs in {
    "NEA": "KR JP CN HK TW MO MN",
    "SEA": "SG TH ID PH MY VN KH MM BN LA",
    "NA": "US CA",
    "EU": "GB IE FR DE IT ES PT NL BE LU AT CH SE NO DK FI PL CZ GR HU RO BG HR SK SI EE LV LT",
}.items():
    for c in cs.split():
        COUNTRY_REGION[c] = r


def get(path, **params):
    params["key"] = os.environ["YOUTUBE_API_KEY"]
    with urllib.request.urlopen(f"{YT_API}/{path}?" + urllib.parse.urlencode(params), timeout=30) as r:
        return json.load(r)


def search(ref, with_lang):
    after = (ref - timedelta(days=WINDOW_DAYS - 1)).isoformat() + "T00:00:00Z"
    before = (ref + timedelta(days=1)).isoformat() + "T00:00:00Z"
    out = defaultdict(set)
    for region, qs in YT_REGION_QUERIES.items():
        for code, lang, q in qs:
            p = {"part": "id", "type": "video", "q": q, "regionCode": code, "order": "date",
                 "maxResults": 50, "publishedAfter": after, "publishedBefore": before}
            if with_lang:
                p["relevanceLanguage"] = lang
            for it in get("search", **p).get("items", []):
                if it.get("id", {}).get("videoId"):
                    out[region].add(it["id"]["videoId"])
    return out


def batched(ids, n=50):
    ids = list(ids)
    for i in range(0, len(ids), n):
        yield ids[i:i + n]


def metrics(assign, truth):
    """assign: region -> set(video); truth: video -> true region or None."""
    regions = list(YT_REGION_QUERIES)
    rows, known, correct = [], 0, 0
    per = {}
    for r in regions:
        vids = assign.get(r, set())
        kn = [v for v in vids if truth.get(v)]
        ok = sum(truth[v] == r for v in kn)
        per[r] = {"n": len(vids), "known": len(kn), "precision": round(ok / len(kn), 3) if kn else None}
        known += len(kn)
        correct += ok
        rows.append([sum(truth[v] == t for v in kn) for t in regions])
    allv = Counter(v for r in regions for v in assign.get(r, set()))
    dup = sum(1 for c in allv.values() if c > 1) / len(allv) if allv else 0.0
    table = [row for row in rows if sum(row)]
    cols = [j for j in range(len(regions)) if sum(row[j] for row in table)]
    table = [[row[j] for j in cols] for row in table]
    chi2 = p = v = None
    if len(table) >= 2 and len(cols) >= 2:
        chi2, p, _, _ = chi2_contingency(table)
        n = sum(map(sum, table))
        v = (chi2 / (n * (min(len(table), len(cols)) - 1))) ** 0.5
    return {"per_region": per, "precision_known": round(correct / known, 3) if known else None,
            "known_share": round(known / sum(len(s) for s in assign.values()), 3) if assign else None,
            "duplication_rate": round(dup, 3),
            "chi2": round(chi2, 2) if chi2 is not None else None,
            "p_value": p, "cramers_v": round(v, 3) if v is not None else None}


def main():
    ref = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    rule_a, rule_b = search(ref, False), search(ref, True)
    vids = set().union(*rule_a.values(), *rule_b.values())
    chan = {}
    for chunk in batched(vids):
        for v in get("videos", part="snippet", id=",".join(chunk)).get("items", []):
            chan[v["id"]] = v["snippet"].get("channelId")
    country = {}
    for chunk in batched({c for c in chan.values() if c}):
        for c in get("channels", part="snippet", id=",".join(chunk)).get("items", []):
            country[c["id"]] = c["snippet"].get("country")
    truth = {v: COUNTRY_REGION.get(country.get(chan.get(v)) or "") for v in vids
             if chan.get(v) != YT_CHANNEL}
    rule_d = defaultdict(set)
    for r, s in rule_b.items():
        for v in s:
            rule_d[truth.get(v) or r].add(v)
    res = {"date": ref.isoformat(), "videos": len(vids),
           "channel_country_known": round(sum(1 for v in vids if truth.get(v)) / len(vids), 3) if vids else 0,
           "A_regioncode_only": metrics(rule_a, truth),
           "B_regioncode_language": metrics(rule_b, truth),
           "D_reassign_by_channel_country": metrics(rule_d, truth)}
    b = res["B_regioncode_language"]
    if b["precision_known"] is not None and b["known_share"] is not None:
        res["D_estimated_overall_precision"] = round(
            b["known_share"] + (1 - b["known_share"]) * b["precision_known"], 3)
    out = Path(__file__).resolve().parent.parent / "data" / "analysis" / f"region-assignment-{ref.isoformat()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
