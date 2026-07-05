---
description: Gucci daily pipeline — per-block collection → sentiment → GMAI index → index interpretation + business review (two separate reports), published as Korean analyst reports.
argument-hint: "[YYYY-MM-DD] (default today)"
---

DATE = $1 or today (YYYY-MM-DD). Execute strictly in order; every stage persists to files. Subagents return short summaries + paths only — never pull raw data into this context.

1. COLLECT (parallel ×4): Use the regional-collector subagent four times IN PARALLEL (one message, four invocations), one per REGION (NEA, SEA, NA, EU), passing REGION and DATE. Each writes data/raw/{DATE}/{REGION}.json.

1.5 SOV (parallel with step 2): use the sov-auditor subagent once, passing DATE. It measures symmetric per-brand counts into data/sov/{DATE}.json — the index script prefers this over collection-derived counts (bias control per §3.2d).

2. SENTIMENT (parallel ×4): after step 1 completes, use the sentiment-classifier subagent per block in parallel (NEA, SEA, NA, EU), passing REGION and DATE. Each writes data/sentiment/{DATE}/{REGION}.json.

3. INDEX: use the index-analyst subagent once, passing DATE. It runs `python scripts/compute_gmai.py {DATE}` — script-computed GMAI, deltas, bands, triggers, component breakdowns. Never compute the index by LLM arithmetic.

4. INTERPRET + REVIEW (parallel ×2, strict separation of duties): in ONE parallel batch,
   (a) use the index-interpreter subagent once, passing DATE — it writes the ONLY report allowed to discuss index numbers → data/reports/daily/{DATE}-index-interpretation.md;
   (b) use the business-reviewer subagent once, passing DATE — business narrative with ZERO index figures → data/reports/daily/{DATE}-gucci-business-review.md.
   Three distinct briefs publish every day: index-interpretation + gucci-business-review (this pipeline) + luxury-brief (/daily-brief). Index talk lives only in (a).

5. GATE (each report separately): use the fact-checker subagent on each draft — for the business review the checker must also FAIL it if any index figure/name (GMAI, NSS, 밴드, 성분 점수, Δ) appears in it. On FAIL, send ONLY the fix list (never the full draft) back to whichever subagent wrote the draft for ONE correction pass, then re-check with the fact-checker subagent. Never publish without PASS.

6. PUBLISH: use the editor-in-chief subagent to finalize BOTH reports (Korean analyst-report format: 제목/목차/핵심 요약/prose sections/EN summary/출처 with all URLs). Then tell the user: both file paths + 3-line core (global GMAI/Δ/band from the interpretation, top driver, top recommendation).

7. TRIGGER LINK: if any §3.5 trigger fired (see data/index/{DATE}.json), flag it at the top of the report and recommend running /event-response (do NOT auto-run; the user decides).
