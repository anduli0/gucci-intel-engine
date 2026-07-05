---
description: Daily brief desk — cross-luxury third-party analysis every day (never a news roundup).
argument-hint: "[YYYY-MM-DD] (default today)"
---

DATE = $1 or today. If run after /daily-gucci, reuse data/index/{DATE}.json (do not recollect).

1. WATCH (parallel ×7, shallow): IN ONE PARALLEL BATCH use (a) the luxury-brand-watcher subagent per group (Kering / LVMH / Hermes-Chanel / Jewelry / Beauty), passing BRAND_GROUP, DATE, MODE=daily — each writes data/luxury/{DATE}/{BRAND_GROUP}.json; (b) the calendar-scout subagent (DATE) → data/calendar/{DATE}.json; (c) the ambassador-tracker subagent (DATE) → data/ambassadors/{DATE}.json.

2. ANALYZE: use the daily-brief-analyst subagent once, passing DATE. Draft → data/reports/daily/{DATE}-luxury-brief.md.

3. Gate: use the fact-checker subagent on the draft; on FAIL, one correction pass via the daily-brief-analyst subagent, then re-check. Then use the editor-in-chief subagent to finalize.

Report to the user: path + 오늘의 한 줄 + 1–2 Gucci implications. If a brand event is large, recommend escalation to /event-response (user decides).
