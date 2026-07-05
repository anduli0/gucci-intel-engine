# Sentiment Rubric — labeling contract for sentiment-classifier

Target = attitude TOWARD the brand, not the writer's mood.

## POSITIVE (+1)

- Praise for design / collections / creative direction
- Ambassador & collaboration enthusiasm
- Purchase intent ("want it", repurchase)
- Resale value / scarcity / quality praise
- Favorable trade-press criticism (BoF, Vogue Business, WWD)

## NEGATIVE (−1)

- Design criticism / "lost its way" narratives
- Price-hike backlash
- Quality / QC complaints
- Value-for-money disputes
- Resale price drops, outlet/discount image damage
- Controversies (campaigns, ambassador risk, sustainability/labor, counterfeits)
- Negative earnings / momentum press

## NEUTRAL (0)

- Plain factual reporting (schedules, appointments, raw figures), questions,
  incidental mentions
- Brand-owned promo copy = 0 (self-praise is not public opinion);
  third-party positive reviews = +1

## Magnitude

- 1.0 = clear, emotional, viral / headline-level
- 0.5 = mild, conditional, incidental

## Activation-coverage discount (v1.1, anti-promo-bias — BINDING)

Coverage OF Gucci's own marketing output (campaign launches, brand-staged
shows/premieres/parties, ambassador appointments, capsule drops, store
openings) is largely press-kit derived and is NOT public opinion about the
brand. The index must not rise merely because Gucci ran more marketing.
- Purely descriptive activation write-up (what it is, who stars, where it
  runs) → 0, even in fashion/lifestyle media.
- Activation write-up WITH the outlet's own clear evaluative verdict → ±1 but
  magnitude CAPPED at 0.5; add tag `activation_coverage`.
- Positive magnitude 1.0 is reserved for INDEPENDENT judgment only: critics'
  runway/collection reviews, quantified third-party demand data (Lyst, resale
  indices, search/sales figures), documented consumer purchase intent, awards.
- Ambassador appointment / fan coverage additionally falls under the fandom
  trap below (≤0.5).
- Negative items are NOT subject to this cap (backlash against an activation
  is organic opinion).

## Balance sanity check

A region where positives outnumber negatives ≥4:1 is a red flag for
collection bias (promotional oversampling), not proof of good sentiment.
Never invent negatives — but re-read the skewed side strictly under the
activation discount, and state in your return summary that the pool skewed
promotional (collector and reports must disclose it).

## Traps

- Sarcasm → judge by context; default neutral if unsure
- Fandom spikes from ambassadors (esp. K/J/C-pop) → distinguish from genuine
  brand affinity; damp repetitive fan-event volume to mag 0.5; exclude
  bot/copy-paste
- "X is better than Gucci" → −1 for Gucci; peer counts go to SOV only
- Counterfeit inquiries → neutral-to-mild-negative

## Output

JSON per item:

{ "id": ..., "region": ..., "sentiment": +1|0|-1, "magnitude": 0.5|1.0,
  "rationale": "one line", "signal_tags": [...], "confidence": 0.0–1.0 }

Rules:
- If confidence < 0.5 and polarity is ±1, demote to 0.
- When in doubt, neutral. Never force polarity.
