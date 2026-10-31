# Source Pool Policy — admission, tiering, dedup, hygiene

## Tiers

- T1 (w = 1.0) trade press & official — BoF, Vogue Business, WWD, Reuters,
  Bloomberg, FT, Gucci/Kering official newsroom-IR-social.
- T2 (w = 0.7) major national/lifestyle media, regional Vogue editions,
  verified expert creators.
- T3 (w = 0.4) general SNS / communities / small influencers — opinion
  thermometer only.
- BLOCK (excluded): bots, spam, counterfeit sellers, plagiarized content,
  hate content, unattributable sources.

## Admission

- Only items directly relevant to target brands with analytical value.
- Primary sources over aggregators.
- Every item MUST have url, published_at, source, tier — otherwise reject.

## Dedup

- Normalize URLs (strip utm parameters); drop exact duplicates.
- Syndicated rewrites → keep the original only and sum reach.
- Retweets / re-uploads → merge engagement into the original, never itemize
  separately.
- CROSS-REGION: one URL may appear in AT MOST ONE region pool per date. If an
  article is relevant to several regions, assign it to the single region it
  covers most directly (publication origin, then subject market). Globally
  syndicated T1 wire stories default to the region of the market they report on.

## Bot filter

- Account-age / follower-ratio anomalies, mass identical phrasing → BLOCK.
- Legit fandom volume stays but is magnitude-damped per the sentiment rubric.

## Data minimization

- No PII stored; public aggregates, summaries, URLs only.
- Respect platform ToS (API / official feeds only where scraping is disallowed).
- Copyright: quote at most one fragment under 15 words per source with
  attribution; everything else paraphrased. Never reproduce song lyrics or
  long passages.
