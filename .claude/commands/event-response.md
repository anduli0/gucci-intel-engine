---
description: Event squad — real-time reaction collection and flash report for shows/launches/controversies, re-runnable per checkpoint.
argument-hint: "\"event name\" [brand=Gucci] [checkpoint=T+2h]"
---

EVENT_NAME = $1 (required); BRAND = $2 or Gucci; CHECKPOINT = $3 or T+2h; EVENT_ID = slug of EVENT_NAME (lowercase, hyphens).

1. Use the event-responder subagent (EVENT_ID, EVENT_NAME, BRAND, CHECKPOINT). If block-level reaction volume warrants it, use the event-responder subagent per region in parallel (max ×4) and merge the results into one flash draft.

2. Gate the flash draft: use the fact-checker subagent (breaking-news items may pass if clearly marked 미확인). Then use the editor-in-chief subagent to finalize.

3. Report to the user: path + 3 lines (direction / top risk / top opportunity).

4. Recommend follow-up checkpoints (T+24h, T+72h with the same EVENT_ID); the final checkpoint report compares the trajectory across checkpoints. Works for non-Gucci brands too (set BRAND); route findings into the daily brief.
