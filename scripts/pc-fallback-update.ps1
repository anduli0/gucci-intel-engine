# Gucci Intelligence - PC last-resort fallback.
# Cloud (GitHub Actions 04:07/06:07/07:07/08:07 KST + claude.ai routine 06:50)
# owns the daily update. This script only acts when ALL cloud paths failed:
#   1) site already shows today's data        -> exit (nothing to do)
#   2) a cloud daily-intelligence run is live -> exit (cloud is handling it)
#   3) otherwise                              -> run the full local pipeline
$ErrorActionPreference = "Continue"
$root = "C:\Users\andul\gucci-intel"
$log  = Join-Path $root "logs\pc-fallback.log"
function L($m) { Add-Content -Path $log -Value ("[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $m) -Encoding UTF8 }

$today = Get-Date -Format "yyyy-MM-dd"
L "check start (today=$today)"

# Gate 1: is the live site already fresh?
try {
    $s = Invoke-RestMethod ("https://anduli0.github.io/gucci-intel-site/api/summary?v=" + (Get-Random)) -TimeoutSec 30
    if ($s.date -eq $today) { L "site already updated ($($s.date)) - no-op"; exit 0 }
    L "site stale (site=$($s.date))"
} catch { L "site check failed: $($_.Exception.Message) - continuing" }

# Gate 2: is a cloud run in progress right now?
try {
    $runs = Invoke-RestMethod "https://api.github.com/repos/anduli0/gucci-intel-engine/actions/runs?status=in_progress&per_page=5" -TimeoutSec 30
    $daily = @($runs.workflow_runs | Where-Object { $_.name -eq "daily-intelligence" })
    if ($daily.Count -gt 0) { L "cloud run in progress (id=$($daily[0].id)) - no-op"; exit 0 }
} catch { L "actions check failed: $($_.Exception.Message) - continuing" }

# Last resort: run the local pipeline (news -> gucci -> brief [-> monday extras] -> publish)
L "LAST RESORT: launching local daily-update.bat"
cmd /c "`"$root\scripts\daily-update.bat`"" >> $log 2>&1
L "local pipeline finished (exit=$LASTEXITCODE)"
exit 0
