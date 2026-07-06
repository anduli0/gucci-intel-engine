---
description: News desk — daily scrap of the 10 most important Gucci news items and 10 most important luxury-industry items, saved as JSON + Korean 개조식 digest.
argument-hint: "[YYYY-MM-DD] (default today)"
---

DATE = $1 or today (YYYY-MM-DD).

1. SCRAP: Use the news-scout subagent once, passing DATE. It searches T1/T2 sources, selects 10 major Gucci items + 10 major luxury items, writes data/news/{DATE}.json and the digest data/news/{DATE}-digest.md. (News is raw material — it never goes into data/reports/, which holds synthesized analysis reports only.)

2. REPORT: tell the user the two file paths, the item counts, the count of SAME-DAY items per set, and the top headline of each set. Freshness rule (binding): the main sets are SAME-DAY (당일) sets — a same-day item always outranks an older one regardless of significance; important non-same-day stories go to the keep archive, not the main sets; 48h and wider windows are top-up only (7-day absolute cap), freshest first, true publication dates always. If the scout reported a shortfall, state it honestly — never pad.

3. ESCALATION: if any single item looks big enough to move the GMAI or demands a reaction (major controversy, CD change, M&A, earnings shock), recommend running /event-response or /daily-gucci — do not auto-run.
