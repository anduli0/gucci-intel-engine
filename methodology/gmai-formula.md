# GMAI Index Contract — Gucci Market Attractiveness Index

GMAI is a 0–100 index, computed per region block plus a global composite.
Region blocks: NEA (Northeast Asia), SEA (Southeast Asia), NA (North America), EU (Europe).
DETERMINISTIC: same inputs must always yield same outputs. All math is done by
`scripts/compute_gmai.py` — never by LLM arithmetic.

## 3.1 Per-item weight

w_i = tier_weight × engagement_weight × recency_weight

- tier_weight: T1 = 1.0, T2 = 0.7, T3 = 0.4
- engagement_weight = min(1.0, log10(1 + reach) / 6); if reach unknown (e.g. news), 0.5
- recency_weight = 0.6^d, where d = whole days since published (today = 0 days → 1.0)

## 3.2 Four components per region (each normalized to 0–1)

(a) Net Sentiment
- s_i ∈ {+1, 0, −1}, magnitude mag_i ∈ {0.5, 1.0}
- NSS_r = Σ(w_i · s_i · mag_i) / Σ(w_i) ∈ [−1, +1]
- Sentiment_r = (NSS_r + 1) / 2

(b) Buzz
- V_today = Σ(w_i) over today's items
- vs 30-day rolling baseline: z = (V_today − μ_30d) / (σ_30d + ε)
- Buzz_r = 1 / (1 + e^(−z))
- If fewer than 5 baseline days exist: Buzz_r = 0.5 (withhold judgment)

(c) Engagement depth
- ratio_i = min(1.0, (likes + 2·comments + 3·shares) / reach × 50); unknown → 0.5
- Engagement_r = Σ(w_i · ratio_i) / Σ(w_i)

(d) Share of Voice
- Competitor set: data/sources/pool.json competitor_set (currently Louis Vuitton,
  Dior, Chanel, Prada, Bottega Veneta, Saint Laurent, Balenciaga, Burberry)
- SOV_r = Gucci_mentions / (Gucci + Σ peers)
- If no counts available → neutral 1/(1 + |competitor_set|)
- COUNTING RULE (bias control): SOV counts MUST come from SYMMETRIC collection —
  the same neutral query template run once per brand ("<brand> news/coverage",
  same period, same outlet universe), counting distinct relevant articles per
  brand. Counts derived from Gucci-targeted collection pools are structurally
  inflated toward Gucci and may only be used as a fallback when no symmetric
  count exists (data/sov/{DATE}.json). The compute script prefers
  data/sov/{DATE}.json over raw-pool mention_counts.

## 3.3 Region sub-index and global composite

GMAI_r = 100 × (0.45·Sentiment + 0.20·Buzz + 0.15·Engagement + 0.20·SOV)

Sentiment carries the top weight so toxic buzz cannot inflate the index.

Global: region_weight = {NEA: 0.35, EU: 0.28, NA: 0.25, SEA: 0.12},
renormalized over available blocks.
GMAI_global = Σ region_weight_r × GMAI_r

## 3.4 Interpretation bands

- 75–100 강한 매력
- 60–74 우호
- 45–59 중립
- 30–44 주의
- 0–29 경고

## 3.5 Triggers (business-reviewer MUST act on these)

Any of:
- |Δ global| ≥ 7 pt
- any block dropping ≥ 10 pt (requires prior block rows)
- any block in 경고 band

→ root-cause analysis is mandatory and the report header flags a recommendation
to run /event-response.

## 3.6 Regression example (self-test; if not reproduced, the pipeline is buggy)

NEA, 3 items:
- i1: T1 news, sentiment +1 × mag 1.0, reach 200,000, published today
  → w = 1.0 × 0.88 × 1.0 = 0.88
- i2: T3 post, sentiment −1 × mag 0.5, reach 50,000, published 1 day ago
  → w = 0.4 × 0.78 × 0.6 ≈ 0.187
- i3: T2 news, sentiment 0, reach unknown, published today
  → w = 0.7 × 0.5 × 1.0 = 0.35

NSS = (0.88 − 0.0935) / 1.417 ≈ 0.555 → Sentiment ≈ 0.777

With Buzz = 0.62, Engagement = 0.55, SOV = 0.18 → GMAI_NEA ≈ 59.2 (중립 upper)

`python scripts/compute_gmai.py --selftest` must reproduce NSS ≈ 0.555 (±0.005)
and GMAI_NEA ≈ 59.2 (±0.2).
