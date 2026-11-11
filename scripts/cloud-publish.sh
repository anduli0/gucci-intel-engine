#!/usr/bin/env bash
# Commit data state to the engine repo (if $1 = commit) and publish site_out/ to
# gucci-intel-site. Called after the core phase AND again after the extras phase,
# so the site is live as soon as core finishes. Needs GH_PAT in the environment.
set -uo pipefail
cd "$(dirname "$0")/.."
git config user.name "gucci-intel-bot"
git config user.email "minkyu494@gmail.com"

if [ "${1:-}" = "commit" ]; then
  git add data
  git commit -m "data: $(date +'%F %H:%M') daily cycle" || echo "no changes"
  git pull --rebase origin main || true
  git push || echo "push skipped"
fi

# Safety: a broken/empty export must never reach --delete (would 404 the live site).
if [ ! -s site_out/index.html ]; then
  echo "ERROR: site_out/index.html missing or empty — aborting publish to protect the live site." >&2
  exit 1
fi
rm -rf site_repo
git clone --depth 1 "https://x-access-token:${GH_PAT}@github.com/anduli0/gucci-intel-site.git" site_repo
# --exclude .github/automation: the site repo keeps its own deploy workflow and docs.
rsync -a --delete --exclude .git --exclude .github --exclude automation site_out/ site_repo/
cd site_repo
git add -A
git commit -m "cloud update $(date +'%F %H:%M')" || echo "no site changes"
for i in 1 2 3 4; do git push && exit 0; git pull --rebase origin main || true; sleep $((2**i)); done
echo "ERROR: site push failed" >&2
exit 1
