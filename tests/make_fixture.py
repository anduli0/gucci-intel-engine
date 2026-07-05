#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Generate a synthetic fixture under tests/sandbox for compute_gmai.py verification.

All items carry "synthetic": true and example.com URLs. Two dates are generated
so that delta and drop-trigger logic is exercised on the second run.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "sandbox"
REGIONS = ["NEA", "SEA", "NA", "EU"]
DATES = ["2026-06-30", "2026-07-01"]

# (tier, sentiment, magnitude, reach) per region per date.
# Day 2 SEA turns hard negative → tests 경고 band + block-drop trigger.
PLans = {
    "2026-06-30": {
        "NEA": [("T1", 1, 1.0, 200000), ("T2", 1, 0.5, 80000), ("T3", 0, 0.5, 30000)],
        "SEA": [("T2", 1, 1.0, 60000), ("T3", 1, 0.5, 20000)],
        "NA":  [("T1", 0, 0.5, None), ("T2", 1, 1.0, 150000), ("T3", -1, 0.5, 40000)],
        "EU":  [("T1", 1, 1.0, 300000), ("T2", 0, 0.5, None)],
    },
    "2026-07-01": {
        "NEA": [("T1", 1, 1.0, 250000), ("T2", 0, 0.5, None), ("T3", 1, 0.5, 25000)],
        "SEA": [("T1", -1, 1.0, 100000), ("T2", -1, 1.0, 70000), ("T3", -1, 1.0, 30000)],
        "NA":  [("T1", 1, 0.5, None), ("T2", 0, 0.5, 90000)],
        "EU":  [("T1", 1, 1.0, 280000), ("T3", 0, 0.5, 15000)],
    },
}
MENTIONS = {"Gucci": 12, "Louis Vuitton": 15, "Dior": 10, "Chanel": 9,
            "Prada": 6, "Bottega Veneta": 4, "Saint Laurent": 5, "Balenciaga": 3}


def main():
    for d in DATES:
        for region in REGIONS:
            items, sents = [], []
            for n, (tier, s, mag, reach) in enumerate(PLans[d][region], 1):
                iid = f"{region.lower()}-{d}-{n:02d}"
                items.append({
                    "synthetic": True, "id": iid, "region": region,
                    "source": f"Synthetic {tier} Outlet", "tier": tier,
                    "url": f"https://example.com/{iid}", "published_at": d,
                    "title": f"Synthetic item {iid}",
                    "summary": "Synthetic fixture item for pipeline verification.",
                    "reach": reach,
                    "likes": None if reach is None else reach // 100,
                    "comments": None if reach is None else reach // 1000,
                    "shares": None if reach is None else reach // 2000,
                })
                sents.append({
                    "id": iid, "region": region, "sentiment": s, "magnitude": mag,
                    "rationale": "synthetic label", "signal_tags": ["synthetic"],
                    "confidence": 0.9,
                })
            raw_dir = ROOT / "data" / "raw" / d
            sent_dir = ROOT / "data" / "sentiment" / d
            raw_dir.mkdir(parents=True, exist_ok=True)
            sent_dir.mkdir(parents=True, exist_ok=True)
            with open(raw_dir / f"{region}.json", "w", encoding="utf-8") as f:
                json.dump({"items": items, "mention_counts": MENTIONS}, f, ensure_ascii=False, indent=2)
            with open(sent_dir / f"{region}.json", "w", encoding="utf-8") as f:
                json.dump(sents, f, ensure_ascii=False, indent=2)
    print(f"fixture written under {ROOT}")


if __name__ == "__main__":
    main()
