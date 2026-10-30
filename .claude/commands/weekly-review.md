---
description: Friday (KST) WEEKLY REVIEW — the full in-depth report of the week across Gucci business, the GMAI index trajectory and the luxury field. The three dailies are short reads; this is where the depth lives.
argument-hint: "[week-end date YYYY-MM-DD, default today]"
---

DATE = $1 or today (YYYY-MM-DD, KST). WEEK_START = DATE minus 6 days.

1. ANALYZE: use the special-analyst subagent with MODE=weekly-review, DATE, WEEK_START, SLUG=weekly-review. It reads the week's three daily report streams (including their 부록), data/index, data/sov, data/luxury, data/news, this week's specials and cards, and writes data/reports/special/{DATE}-weekly-review.md (Korean + ENGLISH EDITION, no length cap).

2. GATE: use the fact-checker subagent on the draft (bilingual cross-check, voice gate, source integrity; the daily LENGTH GATE does not apply to this file). On FAIL, return the fix list to the special-analyst subagent for ONE correction pass, then re-check. Never publish without PASS.

3. PUBLISH: use the editor-in-chief subagent to finalize. Report: path + 3-line core (판정 / 가장 큰 신호 / 최우선 행동).

Rule: this report must stand on its own for a reader who skipped every daily this week.
