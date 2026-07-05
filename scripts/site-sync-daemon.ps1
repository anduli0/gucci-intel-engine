# Gucci Intelligence site-sync daemon.
# Watches data/ and the UI shell every 60s; on any change, publishes to the
# fixed viewer URL repo (publish-site.bat commit no-ops when identical).
$ErrorActionPreference = 'SilentlyContinue'
$root = 'C:\Users\andul\gucci-intel'
$log = Join-Path $root 'logs\site-sync.log'

function State {
    $items = Get-ChildItem -Path (Join-Path $root 'data') -Recurse -File
    $ui = Get-Item (Join-Path $root 'app\ui\index.html')
    $max = ($items + $ui | Measure-Object -Property LastWriteTimeUtc -Maximum).Maximum
    "$($items.Count)|$($max.Ticks)"
}

$last = ''
while ($true) {
    $cur = State
    if ($cur -ne $last) {
        Add-Content $log "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] change detected -> publish"
        & cmd /c "$root\scripts\publish-site.bat" | Out-Null
        $last = State   # re-read: publish itself must not retrigger
    }
    Start-Sleep -Seconds 60
}
