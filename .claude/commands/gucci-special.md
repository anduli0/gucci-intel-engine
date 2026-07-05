---
description: Gucci SPECIAL desk — flagship deep-dive analysis when Gucci holds a fashion show or launches a key product. Fashion shows are the top-priority event type.
argument-hint: ""event name" [YYYY-MM-DD (default today)]"
---

EVENT_NAME = $1 (required). DATE = $2 or today (YYYY-MM-DD). SLUG = kebab-case slug of EVENT_NAME.

1. (Optional, if reactions are fresh and not yet collected) Use the event-responder subagent (EVENT_ID=SLUG, EVENT_NAME, BRAND=Gucci, CHECKPOINT=T+2h) to snapshot real-time reactions into data/events/{SLUG}/.

2. ANALYZE: Use the special-analyst subagent with EVENT_NAME, DATE, SLUG. It reads all on-disk pools plus its own searches and writes the deep-dive to data/reports/special/{DATE}-{SLUG}.md (Korean report prose + English executive summary).

3. GATE: Use the fact-checker subagent on the draft. On FAIL, return the fix list to the special-analyst subagent for ONE correction pass, then re-check. Never publish without PASS.

4. PUBLISH: Use the editor-in-chief subagent to finalize. Report to the user: path + 3-line core (verdict / top signal / top action).
