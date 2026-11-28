# watch-inbox.ps1
# FileSystemWatcher that auto-compiles knowledge blocks when files
# are dropped into harness/inbox/
#
# USAGE:
#   .\watch-inbox.ps1              # run in foreground (Ctrl+C to stop)
#   Start-Process powershell -ArgumentList "-ExecutionPolicy Bypass -File `"$PSScriptRoot\watch-inbox.ps1`"" -WindowStyle Minimized
#
# Drop a file named domain--blockname.txt into harness/inbox/
# and it compiles automatically within 5 seconds.

# Paths default to the Windows install; env overrides let the watcher run (and be
# tested) anywhere without editing the script.

# Resolve roots (env override or derive from location); see _roots.ps1 (#51).
. "$PSScriptRoot\_roots.ps1"
$InboxDir      = if ($env:HARNESS_INBOX_DIR)      { $env:HARNESS_INBOX_DIR }      else { "$HarnessRoot\inbox" }
$ProcessScript = if ($env:HARNESS_PROCESS_SCRIPT) { $env:HARNESS_PROCESS_SCRIPT } else { "$HarnessRoot\scripts\process-inbox.ps1" }
$LogFile       = if ($env:HARNESS_INBOX_LOG)      { $env:HARNESS_INBOX_LOG }      else { "$HarnessRoot\logs\inbox-watcher.log" }

# Ensure log directory exists
$logDir = Split-Path $LogFile
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

function Write-Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $line = "[$ts] $msg"
    Add-Content -Path $LogFile -Value $line
    Write-Host $line
}

Write-Log "Inbox watcher started. Monitoring: $InboxDir"
Write-Log "Drop files as domain--blockname.txt to auto-compile."

# Create watcher
$watcher = New-Object System.IO.FileSystemWatcher
$watcher.Path = $InboxDir
$watcher.Filter = "*.*"
$watcher.IncludeSubdirectories = $false
$watcher.NotifyFilter = [System.IO.NotifyFilters]::FileName -bor [System.IO.NotifyFilters]::LastWrite

# Debounce: track last processed time to avoid double-firing
$script:lastProcessed = @{}

# NOTE: $using: does NOT work inside a Register-ObjectEvent -Action block (it is
# only valid in remote/job/parallel scopes and throws "A Using variable cannot be
# retrieved..."). Paths are passed in via -MessageData and read from $Event.MessageData.
# The whole body is wrapped in try/catch so a failure is logged instead of vanishing
# into the event job's error stream that nobody reads.
$action = {
    try {
        $logFile    = $Event.MessageData.LogFile
        $procScript = $Event.MessageData.ProcessScript

        $name = $Event.SourceEventArgs.Name
        $fullPath = $Event.SourceEventArgs.FullPath
        $changeType = $Event.SourceEventArgs.ChangeType

        # Skip processed/ subdirectory (match either path separator)
        if ($fullPath -match "[\\/]processed[\\/]") { return }

        # Skip non-text files
        if ($name -notmatch "\.(txt|md|log)$") { return }

        # Skip the daily drift-pr--YYYY-MM-DD.md files gemma drops here; they are not
        # knowledge blocks and fail the domain--name regex on every pass (issue #14).
        if ($name -match "^drift-pr--") { return }

        # Debounce: skip if we processed this file in the last 30 seconds.
        # Initialise per-registration state on first fire (the main-scope init does
        # not reach this action's module scope).
        if ($null -eq $script:lastProcessed) { $script:lastProcessed = @{} }
        $now = Get-Date
        if ($script:lastProcessed[$name] -and ($now - $script:lastProcessed[$name]).TotalSeconds -lt 30) {
            return
        }
        $script:lastProcessed[$name] = $now

        # Wait a moment for the file to finish writing
        Start-Sleep -Seconds 2

        $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        $logMsg = "[$ts] File detected: $name ($changeType) - compiling..."
        Add-Content -Path $logFile -Value $logMsg
        Write-Host $logMsg -ForegroundColor Cyan

        & $procScript
        $doneMsg = "[$ts] Compilation complete for: $name"
        Add-Content -Path $logFile -Value $doneMsg
        Write-Host $doneMsg -ForegroundColor Green
    } catch {
        $et = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        $errMsg = "[$et] ERROR in inbox watcher: $_"
        try { Add-Content -Path $Event.MessageData.LogFile -Value $errMsg } catch { }
        Write-Host $errMsg -ForegroundColor Red
    }
}

# Register event handlers. Paths travel in via -MessageData (see the $action note).
$handlerData = @{ LogFile = $LogFile; ProcessScript = $ProcessScript }
Register-ObjectEvent $watcher "Created" -Action $action -MessageData $handlerData | Out-Null
Register-ObjectEvent $watcher "Changed" -Action $action -MessageData $handlerData | Out-Null

# Start watching
$watcher.EnableRaisingEvents = $true

Write-Log "Watcher active. Press Ctrl+C to stop."

# Keep alive
try {
    while ($true) { Start-Sleep -Seconds 1 }
} finally {
    $watcher.EnableRaisingEvents = $false
    $watcher.Dispose()
    Write-Log "Watcher stopped."
}
