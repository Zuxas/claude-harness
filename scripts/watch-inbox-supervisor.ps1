# watch-inbox-supervisor.ps1
# E1: Restart-on-crash supervisor for watch-inbox.ps1.
#
# Runs the inbox watcher in a loop so that if the watcher throws, its runspace
# dies, or it exits for any reason, it is relaunched automatically. Includes a
# tight-crash-loop guard: if the watcher restarts more than 3 times within 60
# seconds, it logs and backs off rather than spinning hot.
#
# ON-LOGIN TASK NOTE:
#   Register THIS script as the on-login Scheduled Task (instead of the raw
#   watch-inbox.ps1) so the inbox watcher always has a supervisor. Task
#   Scheduler is intentionally NOT modified by this script; update the on-login
#   task's command line to point here when ready, e.g.:
#     powershell -ExecutionPolicy Bypass -File "E:\vscode ai project\harness\scripts\watch-inbox-supervisor.ps1"
#
# USAGE:
#   .\watch-inbox-supervisor.ps1

$WatcherScript = Join-Path $PSScriptRoot "watch-inbox.ps1"
$LogFile = "E:\vscode ai project\harness\logs\inbox-watcher-supervisor.log"

# Ensure log directory exists
$logDir = Split-Path $LogFile
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

function Write-SupLog($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] [supervisor] $msg"
    Add-Content -Path $LogFile -Value $line
    Write-Host $line
}

Write-SupLog "Supervisor started. Watcher script: $WatcherScript"

# Tight-crash-loop guard: track restart timestamps over a rolling 60s window.
$restartTimes = New-Object System.Collections.Generic.Queue[datetime]
$BackoffSeconds = 60

while ($true) {
    try {
        Write-SupLog "Launching watcher..."
        & $WatcherScript
        Write-SupLog "Watcher exited (no exception)."
    } catch {
        Write-SupLog "Watcher threw: $_"
    }

    # Record this restart and prune entries older than 60s.
    $now = Get-Date
    $restartTimes.Enqueue($now)
    while ($restartTimes.Count -gt 0 -and ($now - $restartTimes.Peek()).TotalSeconds -gt 60) {
        [void]$restartTimes.Dequeue()
    }

    if ($restartTimes.Count -gt 3) {
        Write-SupLog "Tight crash loop detected ($($restartTimes.Count) restarts in 60s). Backing off $BackoffSeconds s."
        Start-Sleep -Seconds $BackoffSeconds
        $restartTimes.Clear()
    } else {
        Start-Sleep -Seconds 10
    }
}
