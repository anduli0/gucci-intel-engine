---
description: Luxury watch desk — weekly professional report on the global luxury field (Kering/LVMH/Dior/Hermès/jewelry/beauty) and trend structure.
argument-hint: "[week-end date YYYY-MM-DD]"
---

WEEK_END = $1 or today; window = trailing 7 days.

1. WATCH (parallel ×6): use the luxury-brand-watcher subagent per group IN PARALLEL (Kering / LVMH / Hermes-Chanel / Jewelry / Beauty / Independents), passing BRAND_GROUP, DATE=WEEK_END, MODE=weekly. Each writes data/luxury/{WEEK_END}/{BRAND_GROUP}.json.

2. TREND: use the trend-analyst subagent on the accumulated week (data/luxury/* in the 7-day window). Output → data/analysis/{WEEK_END}-trend.md.

3. ASSEMBLE: use the daily-brief-analyst subagent to compose the weekly report: week summary / key moves per brand / category temperature / regional shifts / trend inflections / Gucci threats-opportunities-recommendations. Draft → data/reports/weekly/{WEEK_END}-luxury-weekly.md.

4. Gate: use the fact-checker subagent (weekly run — it also proposes source-pool updates). Then use the editor-in-chief subagent to finalize. Report to the user: path + this week's top-3 implications for Gucci.

Rule: no listing. Everything converges on "so what should Gucci do".
