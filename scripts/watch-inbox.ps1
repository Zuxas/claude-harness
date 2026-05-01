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

$InboxDir = "E:\vscode ai project\harness\inbox"
$ProcessScript = "E:\vscode ai project\harness\scripts\process-inbox.ps1"
$LogFile = "E:\vscode ai project\harness\logs\inbox-watcher.log"

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

$action = {
    $name = $Event.SourceEventArgs.Name
    $fullPath = $Event.SourceEventArgs.FullPath
    $changeType = $Event.SourceEventArgs.ChangeType
    
    # Skip processed/ subdirectory
    if ($fullPath -match "\\processed\\") { return }
    
    # Skip non-text files
    if ($name -notmatch "\.(txt|md|log)$") { return }
    
    # Debounce: skip if we processed this file in the last 30 seconds
    $now = Get-Date
    if ($script:lastProcessed[$name] -and ($now - $script:lastProcessed[$name]).TotalSeconds -lt 30) {
        return
    }
    $script:lastProcessed[$name] = $now
    
    # Wait a moment for the file to finish writing
    Start-Sleep -Seconds 2
    
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $logMsg = "[$ts] File detected: $name ($changeType) - compiling..."
    Add-Content -Path $using:LogFile -Value $logMsg
    Write-Host $logMsg -ForegroundColor Cyan
    
    try {
        & $using:ProcessScript
        $doneMsg = "[$ts] Compilation complete for: $name"
        Add-Content -Path $using:LogFile -Value $doneMsg
        Write-Host $doneMsg -ForegroundColor Green
    } catch {
        $errMsg = "[$ts] ERROR compiling $name`: $_"
        Add-Content -Path $using:LogFile -Value $errMsg
        Write-Host $errMsg -ForegroundColor Red
    }
}

# Register event handlers
Register-ObjectEvent $watcher "Created" -Action $action | Out-Null
Register-ObjectEvent $watcher "Changed" -Action $action | Out-Null

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
