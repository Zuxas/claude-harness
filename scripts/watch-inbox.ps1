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
# E4: per-file lock dir lives OUTSIDE the inbox so it is never picked up by
# process-inbox.ps1's scan nor by this watcher's own events.
$LockDir = "E:\vscode ai project\harness\state\inbox-locks"
# E3: Ollama liveness endpoint (HTTP 200 == server up).
$OllamaTagsUrl = "http://localhost:11434/api/tags"

# Ensure log directory exists
$logDir = Split-Path $LogFile
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir -Force | Out-Null }

# Ensure lock directory exists (E4)
if (-not (Test-Path $LockDir)) { New-Item -ItemType Directory -Path $LockDir -Force | Out-Null }

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
# E2: enlarge the internal buffer (default 8 KB) so bursts of events do not
# overflow it and silently kill the watcher.
$watcher.InternalBufferSize = 65536

# Debounce: track last processed time to avoid double-firing
$script:lastProcessed = @{}
# E4: track files currently being compiled so a Created+Changed double-fire
# within the debounce window cannot start two concurrent compiles of one file.
$script:processing = @{}

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

    # E4: per-file concurrency guard. If a compile for this file is already in
    # flight (Created+Changed double-fire), bail out before doing any work.
    if ($script:processing[$name]) { return }
    $script:processing[$name] = $true
    $lockFile = Join-Path $using:LockDir ($name + ".lock")

    try {
        # Wait a moment for the file to finish writing
        Start-Sleep -Seconds 2

        $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

        # E4: window-scoped lock file (hash identifies the file; removed in
        # finally). Belt-and-suspenders with the in-memory guard above.
        if (Test-Path $fullPath) {
            try {
                $hash = (Get-FileHash -Path $fullPath -Algorithm SHA256).Hash
                Set-Content -Path $lockFile -Value $hash -ErrorAction SilentlyContinue
            } catch { }
        }

        # E3: Ollama precheck. If the server is down, leave the file in the
        # inbox and let the nightly inbox step compile it later.
        $ollamaUp = $false
        try {
            $resp = Invoke-WebRequest -Uri $using:OllamaTagsUrl -UseBasicParsing -TimeoutSec 5
            if ($resp.StatusCode -eq 200) { $ollamaUp = $true }
        } catch {
            $ollamaUp = $false
        }

        if (-not $ollamaUp) {
            $defMsg = "[$ts] File detected: $name ($changeType) - deferred (ollama down); left for nightly inbox step"
            Add-Content -Path $using:LogFile -Value $defMsg
            Write-Host $defMsg -ForegroundColor Yellow
            return
        }

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
    } finally {
        # Release both the in-memory guard and the window-scoped lock file.
        $script:processing.Remove($name)
        if (Test-Path $lockFile) { Remove-Item -Path $lockFile -Force -ErrorAction SilentlyContinue }
    }
}

# E2: Error handler. A buffer overflow raises the Error event; without a
# handler the watcher dies silently. Log the exception and re-arm the watcher.
$errorAction = {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    $ex = $Event.SourceEventArgs.GetException()
    $msg = "[$ts] WATCHER ERROR: $($ex.Message) - re-enabling EnableRaisingEvents"
    Add-Content -Path $using:LogFile -Value $msg
    Write-Host $msg -ForegroundColor Red
    try {
        $Sender.EnableRaisingEvents = $false
        $Sender.EnableRaisingEvents = $true
    } catch {
        $rearmMsg = "[$ts] WATCHER ERROR: re-enable failed: $_"
        Add-Content -Path $using:LogFile -Value $rearmMsg
        Write-Host $rearmMsg -ForegroundColor Red
    }
}

# Register event handlers
Register-ObjectEvent $watcher "Created" -Action $action | Out-Null
Register-ObjectEvent $watcher "Changed" -Action $action | Out-Null
Register-ObjectEvent $watcher "Error" -Action $errorAction | Out-Null

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
