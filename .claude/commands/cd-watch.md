---
description: Creative-director desk — per-brand CD deep-dive dossiers (style, vision, track record, interviews), auto-updated on moves and major interviews. One dossier written or refreshed per run.
argument-hint: "[\"name\" \"brand\"] (default: auto-pick)"
---

NAME = $1, BRAND = $2 (both optional). DATE = today.

1. ROSTER: read data/cd/roster.json (create if missing by researching the current CDs of: Gucci, Louis Vuitton (womens/mens), Dior, Chanel, Balenciaga, Saint Laurent, Bottega Veneta, Prada, Miu Miu, Hermès, Fendi, Celine, Loewe, Givenchy, Valentino, Burberry, McQueen). Verify with sources — CD seats change often.

2. PICK (when NAME not given), in priority order:
   a. BREAKING — a CD appointment/exit/swap announced in the last few days (check data/news/*.json and data/luxury/*): update BOTH affected dossiers and the roster.
   b. INTERVIEW — a major new interview/manifesto by a rostered CD: refresh that dossier with the interview analysis.
   c. COVERAGE GAP — the most Gucci-relevant CD who has no dossier yet in data/reports/cd/ (order: Gucci's own CD first, then direct-competitor CDs: LV, Dior, Chanel, Balenciaga, Saint Laurent, Bottega, Prada/Miu Miu, then the rest).

3. WRITE: use the cd-analyst subagent with NAME, BRAND, DATE → data/reports/cd/{brand-slug}-{name-slug}.md + roster update. When PICK landed on an existing dossier via (a) or (b), pass along ONLY the genuinely new material so the analyst refreshes just that and re-stamps today's meta-line date. If, on inspection, there is no genuinely new material for the picked CD (no move, no new interview, no new collection since the dossier's date), do NOT rewrite the dossier — leave it untouched and fall through to a (c) coverage-gap CD instead. The daily run must never re-stamp an unchanged dossier to today, or the "updated" badge fires with nothing new behind it.

4. GATE: use the fact-checker subagent on the dossier (career facts, dates, figures, quote lengths). On FAIL, one correction pass via the cd-analyst subagent, re-check.

5. PUBLISH: use the editor-in-chief subagent to finalize (house format + append the English edition after the `<!-- ===== ENGLISH EDITION ===== -->` marker — single file). Report: path + 3-line core.

Note: CD dossiers are EVERGREEN — they live in data/reports/cd/ and are exempt from the 14-day retention policy.
