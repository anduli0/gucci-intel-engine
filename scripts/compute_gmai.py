#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GMAI — Gucci Market Attractiveness Index calculator.

Implements methodology/gmai-formula.md exactly. Deterministic: same inputs
always yield same outputs. All file I/O is UTF-8 (Windows cp949 locale must
never leak in).

CLI:
    python scripts/compute_gmai.py YYYY-MM-DD [--root .]
    python scripts/compute_gmai.py --selftest
"""

import argparse
import csv
import json
import math
import sys
from datetime import date, datetime
from pathlib import Path

REGIONS = ["NEA", "SEA", "NA", "EU"]
REGION_WEIGHTS = {"NEA": 0.35, "EU": 0.28, "NA": 0.25, "SEA": 0.12}
TIER_WEIGHTS = {"T1": 1.0, "T2": 0.7, "T3": 0.4}
W_SENT, W_BUZZ, W_ENG, W_SOV = 0.45, 0.20, 0.15, 0.20
EPS = 1e-9
BASELINE_MIN_DAYS = 5
BASELINE_WINDOW = 30
CSV_HEADER = ["date", "region", "GMAI", "NSS", "Buzz", "Engagement", "SOV", "delta", "band"]


def band_of(score):
    if score >= 75:
        return "강한 매력"
    if score >= 60:
        return "우호"
    if score >= 45:
        return "중립"
    if score >= 30:
        return "주의"
    return "경고"


def parse_day(value):
    """Parse a date or ISO datetime string to a date; None if unparseable."""
    if not value:
        return None
    s = str(value).strip()
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def recency_weight(published_at, ref_day):
    """v2.1: half-life 3 days (0.5^(d/3)). The v2 curve (0.6^d, half-life
    ~1.4d) collapsed every weight to ~0 whenever the pool skewed older than a
    few days, silently handing the whole region index to its single freshest
    item. 3 days keeps the index reactive to today's news while letting the
    trailing week provide statistical ballast."""
    pub = parse_day(published_at)
    if pub is None:
        return 0.5 ** (1.0 / 3.0)  # unknown date: assume 1 day old
    d = max(0, (ref_day - pub).days)
    return 0.5 ** (d / 3.0)


def item_weight(item, ref_day):
    """v2 evidence weight: credibility x freshness ONLY (§3.1).
    reach/likes/comments/shares never enter w_i — interaction data lives
    exclusively in the Engagement component."""
    tier = str(item.get("tier", "T3")).upper()
    tw = TIER_WEIGHTS.get(tier, 0.4)
    return tw * recency_weight(item.get("published_at"), ref_day)


# §3.2b Buzz channels: reliability-adjusted multi-channel volume.
CHANNEL_WEIGHTS = {"news": 1.0, "sns": 0.8, "community": 0.6}
CHANNEL_ALIASES = {
    "news": "news", "press": "news", "media": "news", "editorial": "news",
    "sns": "sns", "social": "sns", "x": "sns", "instagram": "sns",
    "tiktok": "sns", "youtube": "sns", "weibo": "sns",
    "community": "community", "forum": "community", "board": "community",
    "reddit": "community", "cafe": "community", "blog": "community",
}


def source_channel(item):
    """source_type -> channel; legacy fallback: T1/T2 -> news, T3 -> community."""
    st = str(item.get("source_type", "") or "").strip().lower()
    if st in CHANNEL_ALIASES:
        return CHANNEL_ALIASES[st]
    tier = str(item.get("tier", "T3")).upper()
    return "news" if tier in ("T1", "T2") else "community"


def engagement_ratio(item):
    """§3.2c: interaction depth for METRIC-BEARING items; None when the item
    carries no reported metrics (v1 returned 0.5, diluting the component)."""
    reach = item.get("reach")
    likes, comments, shares = item.get("likes"), item.get("comments"), item.get("shares")
    if reach in (None, 0) or all(v is None for v in (likes, comments, shares)):
        return None
    try:
        num = float(likes or 0) + 2.0 * float(comments or 0) + 3.0 * float(shares or 0)
        return min(1.0, num / float(reach) * 50.0)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def sigmoid(z):
    z = max(-30.0, min(30.0, z))
    return 1.0 / (1.0 + math.exp(-z))


def load_raw(path):
    """Accept either a bare list of items or {"items": [...], "mention_counts": {...}}."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data, {}
    return data.get("items", []), data.get("mention_counts", {}) or {}


def load_sentiment(path):
    """Accept every classifier output shape ever observed: a bare list of
    records, {"items": [...]}, or a list wrapping one or more {"items": [...]}
    blocks (output drift that silently zeroed a whole region on 2026-07-05)."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        data = data.get("items", [])
    elif isinstance(data, list) and data and isinstance(data[0], dict) and "items" in data[0]:
        merged = []
        for block in data:
            if isinstance(block, dict):
                merged.extend(block.get("items", []) or [])
        data = merged
    return {str(rec.get("id")): rec for rec in data if rec.get("id") is not None}


def sov_neutral(root=None):
    """Neutral SOV = 1/(1+len(competitor_set)); falls back to 1/8."""
    try:
        pool = Path(root or ".") / "data" / "sources" / "pool.json"
        with open(pool, "r", encoding="utf-8") as f:
            n = len(json.load(f).get("competitor_set") or [])
        if n > 0:
            return 1.0 / (1 + n)
    except (OSError, json.JSONDecodeError):
        pass
    return 0.125


def compute_sov(mention_counts, neutral=0.125):
    if not mention_counts:
        return neutral, False
    gucci = mention_counts.get("Gucci")
    if gucci is None:
        return neutral, False
    peers = sum(v or 0 for k, v in mention_counts.items() if k != "Gucci")
    total = (gucci or 0) + peers
    if total <= 0:
        return neutral, False
    return gucci / total, True


def compute_region(items, sent_by_id, mention_counts, ref_day, baseline_v, neutral=0.125):
    """Return the full component breakdown for one region (§3.1-3.3 v2)."""
    weights, wsm = [], 0.0
    weng_num, weng_den = 0.0, 0.0            # metric-bearing items only
    v_today = 0.0                            # multi-channel volume (Buzz input)
    channel_mix = {"news": 0, "sns": 0, "community": 0}
    counts = {"pos": 0, "neu": 0, "neg": 0}
    matched = 0                              # items with a sentiment record
    tag_impact = {}                          # signal_tag -> Σ(w·s·mag)
    for it in items:
        w = item_weight(it, ref_day)
        rec = sent_by_id.get(str(it.get("id")), {})
        if rec:
            matched += 1
        s = rec.get("sentiment", 0) or 0
        mag = rec.get("magnitude", 0.5) or 0.5
        s = 1 if s > 0 else (-1 if s < 0 else 0)
        counts["pos" if s > 0 else ("neg" if s < 0 else "neu")] += 1
        weights.append(w)
        wsm += w * s * mag
        if s != 0:
            for tag in rec.get("signal_tags") or []:
                tag_impact[tag] = tag_impact.get(tag, 0.0) + w * s * mag
        ratio = engagement_ratio(it)
        if ratio is not None:
            weng_num += w * ratio
            weng_den += w
        ch = source_channel(it)
        channel_mix[ch] += 1
        v_today += CHANNEL_WEIGHTS[ch] * recency_weight(it.get("published_at"), ref_day)

    total_w = sum(weights)
    if total_w <= EPS:
        nss, sentiment = 0.0, 0.5
    else:
        nss = wsm / total_w
        sentiment = (nss + 1.0) / 2.0
    # Effective sample size: how many items REALLY carry today's sentiment
    # once recency/tier weighting is applied ((Σw)²/Σw²). eff_n≈1 means one
    # item decides the region — the UI must say so instead of implying breadth.
    sum_w2 = sum(w * w for w in weights)
    eff_n = (total_w * total_w / sum_w2) if sum_w2 > EPS else 0.0
    engagement_known = weng_den > EPS
    engagement = (weng_num / weng_den) if engagement_known else 0.5

    history = [v for _, v in baseline_v]
    if len(history) < BASELINE_MIN_DAYS:
        buzz = 0.5
    else:
        mu = sum(history) / len(history)
        var = sum((v - mu) ** 2 for v in history) / len(history)
        sigma = math.sqrt(var)
        buzz = sigmoid((v_today - mu) / (sigma + EPS))

    sov, sov_known = compute_sov(mention_counts, neutral)
    gmai = 100.0 * (W_SENT * sentiment + W_BUZZ * buzz + W_ENG * engagement + W_SOV * sov)

    # Marketer-facing driver attribution: each signal tag's contribution to the
    # sentiment component, expressed in index POINTS (Σ over tags of one item's
    # tags each get the full item impact; overlapping tags are a feature — the
    # question answered is "which themes moved the needle", not partitioning).
    tag_pts = []
    if total_w > EPS and tag_impact:
        for tag, imp in tag_impact.items():
            pts = 100.0 * W_SENT * (imp / total_w) / 2.0
            tag_pts.append([tag, round(pts, 2)])
        tag_pts.sort(key=lambda x: x[1])
    drivers = {
        "neg": [p for p in tag_pts if p[1] < 0][:4],
        "pos": [p for p in tag_pts if p[1] > 0][::-1][:4],
    }
    return {
        "GMAI": round(gmai, 2),
        "band": band_of(gmai),
        "NSS": round(nss, 4),
        "components": {
            "sentiment": round(sentiment, 4),
            "buzz": round(buzz, 4),
            "engagement": round(engagement, 4),
            "sov": round(sov, 4),
        },
        # point contribution of each component to the 0-100 index
        # (sums to GMAI; the deterministic basis for regional-gap decomposition)
        "contrib": {
            "sentiment": round(100.0 * W_SENT * sentiment, 2),
            "buzz": round(100.0 * W_BUZZ * buzz, 2),
            "engagement": round(100.0 * W_ENG * engagement, 2),
            "sov": round(100.0 * W_SOV * sov, 2),
        },
        "sov_known": sov_known,
        "engagement_known": engagement_known,
        "buzz_known": len(history) >= BASELINE_MIN_DAYS,
        "baseline_days": len(history),
        "sentiment_coverage": round(matched / len(items), 3) if items else None,
        "eff_n": round(eff_n, 1),
        "low_evidence": eff_n < 3.0,
        "drivers": drivers,
        "channel_mix": channel_mix,
        "counts": counts,
        "n_items": len(items),
        "v_today": round(v_today, 4),
    }


def load_baseline(path):
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def prior_gmai(csv_path, region, ref_date_str):
    """Most recent GMAI for region strictly before ref_date_str."""
    if not csv_path.exists():
        return None
    best_day, best_val = None, None
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("region") != region or not row.get("date"):
                continue
            if row["date"] >= ref_date_str:
                continue
            if best_day is None or row["date"] > best_day:
                try:
                    best_day, best_val = row["date"], float(row["GMAI"])
                except (TypeError, ValueError):
                    continue
    return best_val


def prior_components(csv_path, region, ref_date_str):
    """Most recent component row (as 0-1 values) strictly before ref_date_str."""
    if not csv_path.exists():
        return None
    best = None
    with open(csv_path, "r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("region") != region or not row.get("date"):
                continue
            if row["date"] >= ref_date_str:
                continue
            if best is None or row["date"] > best["date"]:
                best = row
    if not best:
        return None
    try:
        return {"sentiment": (float(best["NSS"]) + 1.0) / 2.0,
                "buzz": float(best["Buzz"]),
                "engagement": float(best["Engagement"]),
                "sov": float(best["SOV"])}
    except (KeyError, TypeError, ValueError):
        return None


def run(date_str, root):
    root = Path(root)
    ref_day = date.fromisoformat(date_str)
    raw_dir = root / "data" / "raw" / date_str
    sent_dir = root / "data" / "sentiment" / date_str
    index_dir = root / "data" / "index"
    index_dir.mkdir(parents=True, exist_ok=True)
    baseline_path = index_dir / "baseline_30d.json"
    csv_path = index_dir / "gmai_timeseries.csv"

    # Objective SOV file (symmetric per-brand counts) takes precedence over
    # mention_counts derived from Gucci-targeted collection, which are biased.
    sov_path = root / "data" / "sov" / f"{date_str}.json"
    sov_override = {}
    if sov_path.exists():
        with open(sov_path, "r", encoding="utf-8") as f:
            sov_override = (json.load(f) or {}).get("regions", {})

    baseline = load_baseline(baseline_path)
    results, missing = {}, []
    for region in REGIONS:
        raw_path = raw_dir / f"{region}.json"
        if not raw_path.exists():
            missing.append(region)
            continue
        items, mention_counts = load_raw(raw_path)
        if region in sov_override and sov_override[region]:
            mention_counts = sov_override[region]
        sent_path = sent_dir / f"{region}.json"
        sent_by_id = load_sentiment(sent_path) if sent_path.exists() else {}
        history = [(d, v) for d, v in baseline.get(region, []) if d < date_str][-BASELINE_WINDOW:]
        results[region] = compute_region(items, sent_by_id, mention_counts, ref_day, history,
                                         neutral=sov_neutral(root))
        results[region]["sov_source"] = "objective" if region in sov_override and sov_override[region] else "collection-derived"

    if not results:
        print(f"ERROR: no region data found under {raw_dir}", file=sys.stderr)
        return 1

    # Global composite over available blocks, weights renormalized.
    wsum = sum(REGION_WEIGHTS[r] for r in results)
    global_gmai = sum(REGION_WEIGHTS[r] / wsum * results[r]["GMAI"] for r in results)
    global_gmai = round(global_gmai, 2)

    # Deltas vs most recent prior rows (before touching the CSV).
    deltas = {}
    for region in list(results) + ["GLOBAL"]:
        cur = global_gmai if region == "GLOBAL" else results[region]["GMAI"]
        prev = prior_gmai(csv_path, region, date_str)
        deltas[region] = None if prev is None else round(cur - prev, 2)

    # Delta attribution: how many index points each component contributed to
    # today's move (exact per region; global = region-weighted aggregate,
    # exact when the same region set exists on both days).
    comp_w = {"sentiment": W_SENT, "buzz": W_BUZZ, "engagement": W_ENG, "sov": W_SOV}
    for region, res in results.items():
        prev_c = prior_components(csv_path, region, date_str)
        res["delta_attrib"] = None if prev_c is None else {
            k: round(100.0 * comp_w[k] * (res["components"][k] - prev_c[k]), 2)
            for k in comp_w}
    global_attrib = None
    if all(res.get("delta_attrib") for res in results.values()):
        global_attrib = {
            k: round(sum(REGION_WEIGHTS[r] / wsum * results[r]["delta_attrib"][k]
                         for r in results), 2)
            for k in comp_w}

    # Triggers per §3.5 — structured (for the app to localize) + legacy text.
    triggers, triggers_v2 = [], []
    if deltas["GLOBAL"] is not None and abs(deltas["GLOBAL"]) >= 7:
        triggers.append(f"GLOBAL |Δ| ≥ 7pt (Δ={deltas['GLOBAL']:+.2f})")
        triggers_v2.append({"code": "global_delta", "delta": deltas["GLOBAL"]})
    for region, res in results.items():
        if deltas.get(region) is not None and deltas[region] <= -10:
            triggers.append(f"{region} dropped ≥ 10pt (Δ={deltas[region]:+.2f})")
            triggers_v2.append({"code": "region_drop", "region": region, "delta": deltas[region]})
        if res["band"] == "경고":
            triggers.append(f"{region} in 경고 band (GMAI={res['GMAI']})")
            triggers_v2.append({"code": "band_alert", "region": region, "gmai": res["GMAI"]})

    # Rewrite CSV: keep prior rows for other dates, replace today's (idempotent re-run).
    rows = []
    if csv_path.exists():
        with open(csv_path, "r", encoding="utf-8", newline="") as f:
            rows = [r for r in csv.DictReader(f) if r.get("date") != date_str]
    for region in REGIONS:
        if region not in results:
            continue
        res = results[region]
        rows.append({
            "date": date_str, "region": region, "GMAI": f"{res['GMAI']:.2f}",
            "NSS": f"{res['NSS']:.4f}", "Buzz": f"{res['components']['buzz']:.4f}",
            "Engagement": f"{res['components']['engagement']:.4f}",
            "SOV": f"{res['components']['sov']:.4f}",
            "delta": "" if deltas[region] is None else f"{deltas[region]:+.2f}",
            "band": res["band"],
        })
    global_sent = sum(REGION_WEIGHTS[r] / wsum * results[r]["components"]["sentiment"] for r in results)
    rows.append({
        "date": date_str, "region": "GLOBAL", "GMAI": f"{global_gmai:.2f}",
        "NSS": "", "Buzz": "", "Engagement": "", "SOV": "",
        "delta": "" if deltas["GLOBAL"] is None else f"{deltas['GLOBAL']:+.2f}",
        "band": band_of(global_gmai),
    })
    rows.sort(key=lambda r: (r["date"], r["region"] == "GLOBAL", r["region"]))
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADER)
        writer.writeheader()
        writer.writerows(rows)

    # Update 30-day baseline (replace today's entry if re-run, trim window).
    for region, res in results.items():
        entries = [e for e in baseline.get(region, []) if e[0] != date_str]
        entries.append([date_str, res["v_today"]])
        entries.sort(key=lambda e: e[0])
        baseline[region] = entries[-(BASELINE_WINDOW * 2):]
    with open(baseline_path, "w", encoding="utf-8") as f:
        json.dump(baseline, f, ensure_ascii=False, indent=2)

    # Snapshot.
    snapshot = {
        "date": date_str,
        "regions": {
            r: {**{k: v for k, v in res.items() if k != "v_today"}, "delta": deltas[r]}
            for r, res in results.items()
        },
        "global": {
            "GMAI": global_gmai,
            "band": band_of(global_gmai),
            "delta": deltas["GLOBAL"],
            "delta_attrib": global_attrib,
            "sentiment_weighted": round(global_sent, 4),
        },
        "missing_blocks": missing,
        "triggers": triggers,
        "triggers_v2": triggers_v2,
        "region_weights_used": {r: round(REGION_WEIGHTS[r] / wsum, 4) for r in results},
    }
    snap_path = index_dir / f"{date_str}.json"
    with open(snap_path, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False, indent=2)

    # Compact results table.
    print(f"GMAI {date_str}")
    print(f"{'region':<8}{'GMAI':>8}{'NSS':>9}{'Buzz':>7}{'Eng':>7}{'SOV':>7}{'delta':>8}  band")
    for region in REGIONS:
        if region not in results:
            continue
        res, c = results[region], results[region]["components"]
        d = "-" if deltas[region] is None else f"{deltas[region]:+.2f}"
        print(f"{region:<8}{res['GMAI']:>8.2f}{res['NSS']:>9.4f}{c['buzz']:>7.3f}"
              f"{c['engagement']:>7.3f}{c['sov']:>7.3f}{d:>8}  {res['band']}")
    dg = "-" if deltas["GLOBAL"] is None else f"{deltas['GLOBAL']:+.2f}"
    print(f"{'GLOBAL':<8}{global_gmai:>8.2f}{'':>9}{'':>7}{'':>7}{'':>7}{dg:>8}  {band_of(global_gmai)}")
    if missing:
        print(f"missing blocks (weights renormalized): {', '.join(missing)}")
    if triggers:
        print("TRIGGERS:")
        for t in triggers:
            print(f"  - {t}")
    else:
        print("triggers: none")
    print(f"snapshot: {snap_path}")
    return 0


def selftest():
    """Reproduce methodology §3.6 (v2.1). PASS → exit 0, FAIL → exit 2."""
    ref = date(2026, 1, 2)
    items = [
        {"id": "i1", "tier": "T1", "source_type": "news", "published_at": "2026-01-02"},
        {"id": "i2", "tier": "T3", "source_type": "community", "published_at": "2026-01-01",
         "reach": 50000, "likes": 300, "comments": 20, "shares": 10},
        {"id": "i3", "tier": "T2", "source_type": "news", "published_at": "2026-01-02"},
    ]
    sent = {
        "i1": {"sentiment": 1, "magnitude": 1.0},
        "i2": {"sentiment": -1, "magnitude": 0.5},
        "i3": {"sentiment": 0, "magnitude": 0.5},
    }
    total_w = wsm = 0.0
    weng_num = weng_den = 0.0
    v_today = 0.0
    for it in items:
        w = item_weight(it, ref)
        rec = sent[it["id"]]
        total_w += w
        wsm += w * rec["sentiment"] * rec["magnitude"]
        ratio = engagement_ratio(it)
        if ratio is not None:
            weng_num += w * ratio
            weng_den += w
        v_today += CHANNEL_WEIGHTS[source_channel(it)] * recency_weight(it.get("published_at"), ref)
    nss = wsm / total_w
    sentiment = (nss + 1.0) / 2.0
    engagement = weng_num / weng_den
    gmai = 100.0 * (W_SENT * sentiment + W_BUZZ * 0.62 + W_ENG * engagement + W_SOV * 0.18)

    checks = [
        ("NSS", nss, 0.4170, 0.005),
        ("V_today", v_today, 2.4762, 0.01),
        ("Engagement", engagement, 0.37, 0.005),
        ("GMAI_NEA", gmai, 53.43, 0.2),
    ]
    ok_all = True
    for name, got, target, tol in checks:
        ok = abs(got - target) <= tol
        ok_all = ok_all and ok
        print(f"selftest §3.6 v2.1: {name}={got:.4f} (target {target}±{tol}) {'ok' if ok else 'MISMATCH'}")
    print("PASS" if ok_all else "FAIL")
    return 0 if ok_all else 2


def main():
    if sys.stdout.encoding and sys.stdout.encoding.lower() not in ("utf-8", "utf8"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Compute the GMAI index (methodology/gmai-formula.md).")
    parser.add_argument("date", nargs="?", help="YYYY-MM-DD")
    parser.add_argument("--root", default=".", help="project root (default: current directory)")
    parser.add_argument("--selftest", action="store_true", help="reproduce the §3.6 regression example")
    args = parser.parse_args()

    if args.selftest:
        sys.exit(selftest())
    if not args.date:
        parser.error("date is required unless --selftest")
    try:
        date.fromisoformat(args.date)
    except ValueError:
        parser.error(f"invalid date: {args.date}")
    sys.exit(run(args.date, args.root))


if __name__ == "__main__":
    main()
