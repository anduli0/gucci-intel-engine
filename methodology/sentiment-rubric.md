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
