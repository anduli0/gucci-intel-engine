"""Empirical check of the Engagement interaction weights (likes 1 / comments 2 /
shares 3, gmai-formula.md §3.2c) on the collected earned-media items.

Practitioner claim: comments and shares signal stronger involvement than likes.
Testable implications on our data:
  H1 scarcity   — comments and shares are rarer per exposure than likes
                  (higher effort -> lower base rate), platform by platform.
  H2 marginal   — holding likes fixed, comments/shares still carry
                  information about reach-normalised attention (partial
                  Spearman of log-rates), i.e. they are not redundant with likes.
  H3 stability  — the effort-weighted rate ranks items more consistently than
                  likes-only across the metric-bearing sample (split-half
                  Spearman of the item ranking).
Weights are then compared: (1,1,1), (1,2,3), (1,3,5), scarcity-derived
(1/base-rate, capped), by H3 split-half reliability. Writes
data/analysis/interaction-weights-{DATE}.json. Does NOT change the index.

Usage: python scripts/analyze_interaction_weights.py [YYYY-MM-DD]
"""
import json
import math
import random
import sys
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from scipy.stats import spearmanr

ROOT = Path(__file__).resolve().parent.parent
WINDOW = 30


def load(ref):
    items = {}
    for k in range(WINDOW):
        d = ROOT / "data" / "engagement" / (ref - timedelta(days=k)).isoformat()
        for p in d.glob("*.json") if d.exists() else []:
            if p.stem not in ("NEA", "SEA", "NA", "EU"):
                continue
            for it in json.loads(p.read_text(encoding="utf-8")).get("items", []):
                if it.get("media", "earned") == "earned" and it.get("reach"):
                    items[it["id"]] = it
    return list(items.values())


def rate(it, w):
    x = sum(wi * float(it.get(k) or 0) for wi, k in zip(w, ("likes", "comments", "shares")))
    return math.log1p(x / float(it["reach"]) * 1e4)


def split_half(items, w, reps=200, seed=1):
    """Reliability proxy: Spearman between item ranks under w computed on two
    random halves of the *reach* denominator noise model is not available, so
    we use the standard proxy: rank agreement between w and a jittered w
    (±25 % per weight) over random half-samples — how sensitive the ranking is
    to the exact weights. Higher = weights matter less (robust)."""
    rng = random.Random(seed)
    cors = []
    for _ in range(reps):
        half = rng.sample(items, max(10, len(items) // 2))
        wj = [max(0.0, wi * rng.uniform(0.75, 1.25)) for wi in w]
        a = [rate(i, w) for i in half]
        b = [rate(i, wj) for i in half]
        r = spearmanr(a, b).correlation
        if not math.isnan(r):
            cors.append(r)
    return sum(cors) / len(cors) if cors else None


def partial_spearman(x, y, z):
    """Spearman(x,y | z) via residual ranks (first-order)."""
    rxy, rxz, ryz = (spearmanr(x, y).correlation, spearmanr(x, z).correlation, spearmanr(y, z).correlation)
    den = math.sqrt((1 - rxz ** 2) * (1 - ryz ** 2))
    return (rxy - rxz * ryz) / den if den > 1e-9 else None


def main():
    ref = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    items = load(ref)
    by_pf = defaultdict(list)
    for it in items:
        by_pf[it["platform"]].append(it)
    res = {"date": ref.isoformat(), "items": len(items), "platforms": {}}
    for pf, its in by_pf.items():
        n = len(its)
        base = {}
        for k in ("likes", "comments", "shares"):
            have = [i for i in its if i.get(k) is not None]
            base[k] = {"n": len(have),
                       "per_1k_reach_median": (sorted(float(i[k]) / i["reach"] * 1000 for i in have)[len(have) // 2]
                                               if have else None),
                       "mean": (sum(float(i[k]) for i in have) / len(have)) if have else None}
        # H2: does comments (and shares) add information beyond likes about attention?
        both = [i for i in its if i.get("likes") is not None and i.get("comments") is not None]
        h2 = {}
        if len(both) >= 15:
            lk = [math.log1p(i["likes"]) for i in both]
            cm = [math.log1p(i["comments"]) for i in both]
            rc = [math.log1p(i["reach"]) for i in both]
            h2["n"] = len(both)
            h2["spearman_likes_comments"] = round(spearmanr(lk, cm).correlation, 3)
            h2["partial_reach_comments_given_likes"] = (round(partial_spearman(rc, cm, lk), 3)
                                                        if partial_spearman(rc, cm, lk) is not None else None)
            sh = [i for i in both if i.get("shares") is not None]
            if len(sh) >= 15:
                s = [math.log1p(i["shares"]) for i in sh]
                l2 = [math.log1p(i["likes"]) for i in sh]
                r2 = [math.log1p(i["reach"]) for i in sh]
                h2["partial_reach_shares_given_likes"] = (round(partial_spearman(r2, s, l2), 3)
                                                          if partial_spearman(r2, s, l2) is not None else None)
                h2["spearman_likes_shares"] = round(spearmanr(l2, s).correlation, 3)
        # scarcity-derived weights: inverse median base rate relative to likes, capped at 5
        sw = [1.0]
        for k in ("comments", "shares"):
            bl, bk = base["likes"]["per_1k_reach_median"], base[k]["per_1k_reach_median"]
            sw.append(min(5.0, bl / bk) if bl and bk else None)
        schemes = {"1-1-1": (1, 1, 1), "1-2-3": (1, 2, 3), "1-3-5": (1, 3, 5)}
        if all(v is not None for v in sw):
            schemes["scarcity"] = tuple(round(v, 2) for v in sw)
        h3 = {}
        mb = [i for i in its if i.get("likes") is not None]
        if len(mb) >= 20:
            for nm, w in schemes.items():
                h3[nm] = {"weights": list(w), "rank_robustness": round(split_half(mb, w), 3)}
        res["platforms"][pf] = {"n": n, "H1_base_rates": base, "H2_marginal_information": h2,
                                "H3_rank_robustness": h3}
    out = ROOT / "data" / "analysis" / f"interaction-weights-{ref.isoformat()}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
