---
description: Daily brief desk — the Luxury Watch collects EVERYTHING happening in the luxury world today (6 brand groups incl. Independents), and the luxury brief synthesizes ALL of it into one industry-wide analysis (never a news roundup, never Gucci-centric).
argument-hint: "[YYYY-MM-DD] (default today)"
---

DATE = $1 or today.

1. WATCH (parallel ×8, shallow): IN ONE PARALLEL BATCH use (a) the luxury-brand-watcher subagent per group (Kering / LVMH / Hermes-Chanel / Jewelry / Beauty / Independents), passing BRAND_GROUP, DATE, MODE=daily — each writes data/luxury/{DATE}/{BRAND_GROUP}.json (same-day signals first; the desk tracks every corner of the luxury field every day); (b) the calendar-scout subagent (DATE) → data/calendar/{DATE}.json; (c) the ambassador-tracker subagent (DATE) → data/ambassadors/{DATE}.json.

2. ANALYZE: use the daily-brief-analyst subagent once, passing DATE. It synthesizes ALL of today's watch files into an industry-wide brief — the luxury world as a whole, not a Gucci report (Gucci deep-dives live in the 구찌 비즈니스 리뷰). Draft → data/reports/daily/{DATE}-luxury-brief.md.

3. Gate: use the fact-checker subagent on the draft; on FAIL, one correction pass via the daily-brief-analyst subagent, then re-check. Then use the editor-in-chief subagent to finalize.

Report to the user: path + 오늘의 한 줄 + the day's top 2 industry stories. If a brand event is large, recommend escalation to /event-response (user decides).
