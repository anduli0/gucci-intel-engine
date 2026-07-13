#!/usr/bin/env bash
# Gucci Intelligence — cloud daily cycle (GitHub Actions, Ubuntu).
# Mirrors scripts/daily-update.bat: news -> daily-gucci -> daily-brief,
# Mondays add products + weekly, then retention + static export.
set -uo pipefail
cd "$(dirname "$0")/.."

run_step() {
  echo "===== $1 ($(date +'%F %T')) ====="
  claude -p "$1" --dangerously-skip-permissions || echo "WARN: step failed: $1"
}

run_step "/news-scrap"
run_step "/daily-gucci"
run_step "/daily-brief"
run_step "/cd-watch"

# Special/Event desk cadence guard: a fresh deep-dive at least every 3 days.
# Content dates (see special_age.py), NOT os.path.getmtime — a fresh checkout
# resets every mtime, so an mtime-based age would always read ~0 and never fire.
if ! python scripts/special_age.py; then
  run_step "/gucci-special auto"
fi

if [ "$(date +%u)" = "1" ]; then
  run_step "/gucci-products"
  run_step "/weekly-luxury"
fi

python scripts/retention_cleanup.py || true

# Static export pulls from a live local server
python app/server.py --port 8790 &
SRV=$!
sleep 3
EXPORT_OUT="$PWD/site_out" python scripts/export_static.py
kill "$SRV" 2>/dev/null || true

echo "cloud daily cycle complete ($(date +'%F %T'))"
