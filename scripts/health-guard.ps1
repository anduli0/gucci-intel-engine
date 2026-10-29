# Gucci Intelligence health guard — probes both app servers and revives them.
# Registered as a 30-minute scheduled task (pattern shared with WatcherHealthGuard).
$ErrorActionPreference = 'SilentlyContinue'
$root = 'C:\Users\andul\gucci-intel'
$log = Join-Path $root 'logs\health-guard.log'

function Probe($url) {
    try { (Invoke-WebRequest $url -UseBasicParsing -TimeoutSec 8).StatusCode -eq 200 } catch { $false }
}
function Note($msg) { Add-Content -Path $log -Value "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $msg" }

# Full app (8790)
if (-not (Probe 'http://127.0.0.1:8790/api/status')) {
    Get-NetTCPConnection -LocalPort 8790 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
    Start-Process pythonw -ArgumentList "$root\app\server.py" -WindowStyle Hidden
    Note 'restarted full app server (8790)'
}

# Read-only viewer (8791) — this one backs the public Tailscale share
if (-not (Probe 'http://127.0.0.1:8791/api/status')) {
    Get-NetTCPConnection -LocalPort 8791 -State Listen | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }
    Start-Process pythonw -ArgumentList "$root\app\server.py", '--readonly', '--port', '8791' -WindowStyle Hidden
    Note 'restarted read-only viewer (8791)'
}

# Site sync: RETIRED 2026-07-30. The cloud CI (anduli0/gucci-intel-engine
# daily.yml) is the sole publisher of the live site, so routine local
# publishing was removed here to stop the PC from clobbering fresh cloud data
# with a stale local export. The genuine last-resort local publish still runs
# via pc-fallback-update.ps1 (gated: only when all cloud paths have failed).
# To re-enable local auto-publish, restore the publish-site.bat call below.
