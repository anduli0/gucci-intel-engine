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

# Alarm (independent of GitHub): if the site is still stale at 11:00+ and no
# cloud run is live, pop a desktop warning once a day with the latest cloud
# result. GitHub's own failure mail can't fire when Actions itself is blocked.
$marker = Join-Path $root "logs\stale-alert-$today.flag"
if ((Get-Date).Hour -ge 11 -and -not (Test-Path $marker)) {
    $last = "unknown"
    try {
        $r = (Invoke-RestMethod "https://api.github.com/repos/anduli0/gucci-intel-engine/actions/runs?per_page=1" -TimeoutSec 30).workflow_runs[0]
        $last = "$($r.conclusion) ($($r.created_at))"
    } catch {}
    $msg = "Gucci Intel site is stale (site=$($s.date), today=$today).`nLast cloud run: $last`nstartup_failure = check GitHub account (email/billing). failure = check token/logs."
    New-Item -ItemType File -Path $marker -Force | Out-Null
    L "ALERT shown: $($msg -replace "`n", ' | ')"
    Start-Process powershell -WindowStyle Hidden -ArgumentList "-NoProfile", "-Command", "(New-Object -ComObject WScript.Shell).Popup('$($msg -replace "'", "''")', 0, 'Gucci Intel - update stalled', 48)"
}

# Gate 3: is claude logged in on this PC? (otherwise every step prints
# "Not logged in" and the run only republishes old data)
$auth = (& claude -p "Reply with exactly: AUTH_OK" 2>&1 | Out-String)
if ($auth -notmatch "AUTH_OK") { L "claude not logged in on PC - skip local pipeline (cloud owns the update)"; exit 0 }

# Sync: start from the cloud's latest data so a local publish can never
# overwrite fresher cloud data with a stale clone. Local leftovers are stashed.
Push-Location $root
git stash push -u -m "pc-fallback autostash $today" 2>&1 | Out-Null
git pull --ff-only origin main 2>&1 | Out-Null
$synced = ($LASTEXITCODE -eq 0)
Pop-Location
if (-not $synced) { L "git pull --ff-only failed - skip local pipeline to avoid a stale publish"; exit 0 }

# Last resort: run the local pipeline (news -> gucci -> brief [-> monday extras] -> publish)
L "LAST RESORT: launching local daily-update.bat"
cmd /c "`"$root\scripts\daily-update.bat`"" >> $log 2>&1
L "local pipeline finished (exit=$LASTEXITCODE)"
exit 0
