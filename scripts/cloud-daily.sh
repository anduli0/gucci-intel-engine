#!/usr/bin/env bash
# Gucci Intelligence — cloud daily cycle (GitHub Actions, Ubuntu).
# Mirrors scripts/daily-update.bat: news -> daily-gucci -> daily-brief,
# Mondays add products + weekly, then retention + static export.
set -uo pipefail
cd "$(dirname "$0")/.."

# CORE steps must succeed. A failure here (e.g. a revoked/expired auth token
# returning "401 OAuth access token has been revoked") is fatal: we mark the
# run FAILED so the job goes red and the owner is alerted, instead of silently
# republishing yesterday's data as if the cycle succeeded.
CORE_FAILED=0
run_core() {
  echo "===== $1 ($(date +'%F %T')) ====="
  if ! claude -p "$1" --dangerously-skip-permissions; then
    echo "::error::CORE step failed: $1"
    CORE_FAILED=1
  fi
}

# OPTIONAL steps: a failure is logged but does not fail the whole cycle.
run_opt() {
  echo "===== $1 ($(date +'%F %T')) ====="
  claude -p "$1" --dangerously-skip-permissions || echo "WARN: optional step failed: $1"
}

run_core "/news-scrap"
run_core "/daily-gucci"
run_core "/daily-brief"
run_opt  "/cd-watch"

# Special/Event desk cadence guard: a fresh deep-dive at least every 3 days.
# Content dates (see special_age.py), NOT os.path.getmtime — a fresh checkout
# resets every mtime, so an mtime-based age would always read ~0 and never fire.
if ! python scripts/special_age.py; then
  run_opt "/gucci-special auto"
fi

if [ "$(date +%u)" = "1" ]; then
  run_opt "/gucci-products"
  run_opt "/weekly-luxury"
fi

# Honesty gate: the cycle only "succeeded" if today's daily brief was actually
# produced. This is the same artifact daily.yml's guard checks. If it is missing
# (auth failure, crash, etc.) abort BEFORE export/publish so the live site is
# never overwritten with stale data under a green checkmark.
TODAY_BRIEF="data/reports/daily/$(date +%F)-luxury-brief.md"
if [ "$CORE_FAILED" != "0" ] || [ ! -s "$TODAY_BRIEF" ]; then
  echo "::error::daily cycle did NOT complete — core_failed=$CORE_FAILED, missing/empty $TODAY_BRIEF. Aborting before publish."
  exit 1
fi

python scripts/retention_cleanup.py || true

# Static export pulls from a live local server
python app/server.py --port 8790 &
SRV=$!
sleep 3
EXPORT_OUT="$PWD/site_out" python scripts/export_static.py
kill "$SRV" 2>/dev/null || true

echo "cloud daily cycle complete ($(date +'%F %T'))"
