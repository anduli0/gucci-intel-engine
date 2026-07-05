# GMAI Index Contract — Gucci Market Attractiveness Index (v2.1)

GMAI is a 0–100 index, computed per region block plus a global composite.
Region blocks: NEA (Northeast Asia), SEA (Southeast Asia), NA (North America), EU (Europe).
DETERMINISTIC: same inputs must always yield same outputs. All math is done by
`scripts/compute_gmai.py` — never by LLM arithmetic.

CHANGELOG v2.1 (2026-07-05, same-day patch): recency half-life relaxed from
0.6^d (~1.4 days) to 0.5^(d/3) (3 days). The v2 curve collapsed all weights to
~0 whenever the pool skewed older than a few days, silently handing a region's
entire index to its single freshest item (observed: NEA 07-05 effectively
decided by 1 of 12 items). v2.1 also enriches the snapshot with marketer-facing
diagnostics — none of which change the score itself:
- sentiment_coverage: share of pooled items that actually received a sentiment
  label (detects classifier output failures, which zeroed NEA on 07-05),
- eff_n ((Σw)²/Σw²) and low_evidence (eff_n < 3): how many items REALLY carry
  the weighted result; the UI must disclose thin evidence,
- buzz_known/baseline_days, engagement_known: which components are live vs
  held neutral at 0.5,
- drivers: per-region top ± signal_tags with their sentiment-point impact
  (100·0.45·(Σ_tag w·s·mag / Σw)/2) — "which themes moved the needle",
- delta_attrib: day-over-day index-point change split by component (exact per
  region from the prior CSV row; global = region-weighted aggregate, exact
  when the region set is unchanged).
Sentiment-file robustness: the loader accepts a bare list, {"items":[...]},
or a list wrapping {"items":[...]} blocks. The classifier contract remains
"one flat JSON array of records, each carrying the item id".

CHANGELOG v2 (2026-07-05): strict separation of Buzz (conversation VOLUME) and
Engagement (interaction DEPTH), which v1 conflated three ways: reach sat inside
the per-item weight (contaminating Sentiment and Buzz), Buzz inherited tier and
reach (so it measured credibility-weighted attention, not volume), and unknown
engagement items were averaged in at 0.5 (pinning Engagement to ~0.5 forever).
v2 also makes Buzz explicitly MULTI-CHANNEL: news + SNS + community, not news
only. The volume baseline was reset at the switch (only 2 v1 days existed;
Buzz correctly holds 0.5 until 5 v2 days accumulate). Deltas that straddle the
switch date carry a small formula-change component — interpret with care once.

SEPARATION PRINCIPLE (binding): Buzz answers "HOW MUCH is Gucci being talked
about" and may only consume item COUNTS (channel- and recency-weighted) — never
likes/comments/shares/reach. Engagement answers "HOW STRONGLY do people react
per piece of content" and may only consume per-item interaction metrics — never
item counts. No metric may feed both components.

## 3.1 Per-item evidence weight (used for Sentiment and for weighting
## metric-bearing items inside Engagement — nothing else)

w_i = tier_weight × recency_weight

- tier_weight: T1 = 1.0, T2 = 0.7, T3 = 0.4 (source credibility)
- recency_weight = 0.5^(d/3), where d = whole days since published (today = 0
  → 1.0; 3 days → 0.5; 1 week → ~0.2; 1 month → ~0.001). Unknown date is
  treated as 1 day old.
- reach/likes/comments/shares do NOT enter w_i (v1 did; that double-counted
  interaction into every component).

## 3.2 Four components per region (each normalized to 0–1)

(a) Net Sentiment
- s_i ∈ {+1, 0, −1}, magnitude mag_i ∈ {0.5, 1.0}
- NSS_r = Σ(w_i · s_i · mag_i) / Σ(w_i) ∈ [−1, +1]
- Sentiment_r = (NSS_r + 1) / 2

(b) Buzz — multi-channel conversation volume
- Every item carries source_type ∈ {news, sns, community}.
  news = editorial media (T1/T2 press, official releases); sns = public posts
  on X/Instagram/TikTok/YouTube/Weibo etc.; community = forums & boards
  (Reddit, PurseForum, Naver cafe/blog, 디시 등).
  Fallback when source_type is missing (legacy items): T1/T2 → news, T3 → community.
- Channel reliability weights (bot/spam dampening): news 1.0, sns 0.8, community 0.6.
- V_today = Σ channel_weight(source_type_i) × recency_weight_i over today's pool
  (NO tier weight, NO reach — pure reliability-adjusted volume).
- vs 30-day rolling baseline of V_today: z = (V_today − μ_30d) / (σ_30d + ε)
- Buzz_r = 1 / (1 + e^(−z))
- If fewer than 5 baseline days exist: Buzz_r = 0.5 (withhold judgment)
- The snapshot records channel_mix (item counts per channel) for transparency.

(c) Engagement depth — interaction per piece of content, metric-bearing items ONLY
- An item is metric-bearing iff reach > 0 AND at least one of likes/comments/
  shares is reported by the source. All other items are EXCLUDED (v1 averaged
  them in at 0.5, which buried the signal).
- ratio_i = min(1.0, (likes + 2·comments + 3·shares) / reach × 50)
- Engagement_r = Σ(w_i · ratio_i) / Σ(w_i) over metric-bearing items only
- If no metric-bearing items exist: Engagement_r = 0.5 (withhold judgment) and
  the snapshot flags engagement_known = false.

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
- i1: T1 news (source_type news), sentiment +1 × mag 1.0, published today
  → w = 1.0 × 1.0 = 1.0
- i2: T3 community post (source_type community), sentiment −1 × mag 0.5,
  published 1 day ago, reach 50,000, likes 300, comments 20, shares 10
  → w = 0.4 × 0.5^(1/3) ≈ 0.3175
- i3: T2 news (source_type news), sentiment 0, no metrics, published today
  → w = 0.7 × 1.0 = 0.7

NSS = (1.0·1·1.0 + 0.3175·(−1)·0.5 + 0.7·0·0.5) / (1.0 + 0.3175 + 0.7)
    = 0.8413 / 2.0175 ≈ 0.4170 → Sentiment ≈ 0.7085

Buzz volume: V_today = 1.0·1.0 (i1) + 1.0·1.0 (i3) + 0.6·0.7937 (i2) ≈ 2.4762
(baseline < 5 days in the example, so the composite below takes Buzz as given)

Engagement: only i2 is metric-bearing.
ratio_i2 = min(1, (300 + 2·20 + 3·10)/50,000 × 50) = min(1, 0.37) = 0.37
Engagement = 0.37

With Buzz = 0.62 (given), SOV = 0.18 → GMAI_NEA
= 100 × (0.45·0.7085 + 0.20·0.62 + 0.15·0.37 + 0.20·0.18) ≈ 53.43 (중립)

`python scripts/compute_gmai.py --selftest` must reproduce NSS ≈ 0.4170 (±0.005),
V_today ≈ 2.4762 (±0.01), Engagement = 0.37 (±0.005), GMAI_NEA ≈ 53.43 (±0.2).
