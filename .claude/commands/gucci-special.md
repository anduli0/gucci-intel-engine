---
description: Gucci SPECIAL desk — flagship deep-dive analysis when Gucci holds a fashion show or launches a key product, or (auto mode) on the most significant current development. This desk guarantees a fresh deep-dive AT LEAST every 3 days. Fashion shows are the top-priority event type.
argument-hint: ""event name" | auto [YYYY-MM-DD (default today)]"
---

EVENT_NAME = $1. DATE = $2 or today (YYYY-MM-DD). SLUG = kebab-case slug of EVENT_NAME.

AUTO MODE ($1 empty or "auto"): pick the topic yourself — read the last 3 days of data/news/*.json, data/luxury/*/, data/calendar/*.json and data/raw/*/ and choose the single most significant CURRENT development worth a flagship deep-dive. Priority order: (1) a Gucci show/launch that just happened or is imminent, (2) an EMERGING SIGNAL — a new Gucci line, product family, campaign platform or creative motif that is quietly gaining momentum across recent coverage (multiple mentions across days/channels/regions) but has not yet been analyzed; spotting these BEFORE they become obvious is this desk's core value (example: the Monte Carlo line surfacing through campaign chapters in July 2026), (3) a BRAND IDENTITY / DIRECTION shift — a stated repositioning, new brand platform, manifesto, visual-identity overhaul or strategic pivot by Gucci or a key competitor, (4) a competitor show/CD debut that directly benchmarks Gucci (e.g. couture debuts), (5) a major structural story (M&A, earnings shock, regulatory action, ambassador shift). Emerging-signal check is MANDATORY every run: scan the Gucci news set for recurring names of lines/products/campaigns and diff against data/reports/special/ to see what has never been deep-dived. Set EVENT_NAME to the chosen topic and proceed. Never skip for "no news" — 3 days of luxury always contains one story worth deep analysis. This desk must publish at least one special every 3 days (the daily pipeline enforces the cadence).

1. (Optional, if reactions are fresh and not yet collected) Use the event-responder subagent (EVENT_ID=SLUG, EVENT_NAME, BRAND=Gucci, CHECKPOINT=T+2h) to snapshot real-time reactions into data/events/{SLUG}/.

2. ANALYZE: Use the special-analyst subagent with EVENT_NAME, DATE, SLUG. It reads all on-disk pools plus its own searches and writes the deep-dive to data/reports/special/{DATE}-{SLUG}.md (Korean report prose + English executive summary).

3. GATE: Use the fact-checker subagent on the draft. On FAIL, return the fix list to the special-analyst subagent for ONE correction pass, then re-check. Never publish without PASS.

4. PUBLISH: Use the editor-in-chief subagent to finalize. Report to the user: path + 3-line core (verdict / top signal / top action).
