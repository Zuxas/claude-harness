# register-harness-tasks.ps1
# Registers Windows Task Scheduler entries for harness automation.
# MUST be run as Administrator.
#
# USAGE:
#   .\register-harness-tasks.ps1          # register all tasks
#   .\register-harness-tasks.ps1 -Remove  # remove all harness tasks
#
# Last updated: 2026-04-27 -- snapshot + drift PR moved to early morning
# (4:30am / 4:50am) so handoff state is fresh when user starts the day.
# Nightly harness stays at 17:30/18:30 because it depends on the 5pm
# meta-analyzer scraper.

param(
    [switch]$Remove
)

$HarnessRoot = "E:\vscode ai project\harness"

$Tasks = @(
    @{
        Name     = "Zuxas-Harness-Nightly"
        Desc     = "5:30 PM daily - detect meta shifts, retune APLs, parse MTGA logs, process inbox"
        Action   = "powershell.exe"
        Args     = "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$HarnessRoot\scripts\nightly-harness.ps1`""
        Trigger  = "daily"
        Time     = "17:30"
    },
    @{
        Name     = "Zuxas-Harness-Nightly-Standard"
        Desc     = "6:30 PM daily - nightly harness for Standard format"
        Action   = "powershell.exe"
        Args     = "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$HarnessRoot\scripts\nightly-harness.ps1`" -Format standard"
        Trigger  = "daily"
        Time     = "18:30"
    },
    @{
        Name     = "Zuxas-Harness-InboxWatcher"
        Desc     = "On login - watches inbox folder for new files to compile"
        Action   = "powershell.exe"
        Args     = "-ExecutionPolicy Bypass -WindowStyle Minimized -File `"$HarnessRoot\scripts\watch-inbox.ps1`""
        Trigger  = "logon"
    },
    @{
        # Updated 2026-04-27 -- moved from 23:00 to 04:30. Shift-handoff
        # snapshot pattern from Anthropic effective-harness post. Captures
        # state in the early morning so when user sits down to work, latest-
        # snapshot.md reflects the freshest possible handoff (overnight
        # commits, drift findings, lint state all current).
        Name     = "Zuxas-Harness-SessionSnapshot"
        Desc     = "4:30 AM daily - regenerate latest-snapshot.md with drift findings + lint state"
        Action   = "powershell.exe"
        Args     = "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$HarnessRoot\scripts\session-snapshot.ps1`" -RunDriftDetect -RunLint -RouteDriftFindings"
        Trigger  = "daily"
        Time     = "04:30"
    },
    @{
        # Backstop in case the 4:30am slot was missed (PC off / asleep).
        # Snapshot is idempotent enough that running on next login is fine --
        # the timestamped snapshot just captures whenever-it-was. The 12h
        # threshold prevents thrashing on multiple logins per day.
        Name     = "Zuxas-Harness-SessionSnapshot-Login"
        Desc     = "On login - regenerate snapshot if last snapshot is older than 12 hours"
        Action   = "powershell.exe"
        Args     = "-ExecutionPolicy Bypass -WindowStyle Hidden -Command `"& { `$latest = '$HarnessRoot\state\latest-snapshot.md'; if ((Test-Path `$latest) -and ((Get-Date) - (Get-Item `$latest).LastWriteTime).TotalHours -lt 12) { exit 0 }; & '$HarnessRoot\scripts\session-snapshot.ps1' -RunDriftDetect -RunLint -RouteDriftFindings }`""
        Trigger  = "logon"
    },
    @{
        # Updated 2026-04-27 -- moved from 23:30 to 04:50. Tier 3 Gemma drift
        # PR pattern from OpenAI Codex harness-engineering blog post. Reads
        # day's harness state (snapshot, git log, drift, imperfections, specs)
        # and produces a structured recommendation report at
        # harness/inbox/drift-pr--YYYY-MM-DD.md. Runs at 04:50, 20 minutes
        # after the 04:30 snapshot completes -- gives Gemma a stable, freshly-
        # written snapshot to consume. ~$0.00 cost (local Gemma 4 12B via
        # Ollama). Typical runtime: 90-150 seconds.
        Name     = "Zuxas-Harness-DriftPR"
        Desc     = "4:50 AM daily - Gemma generates next-session drift PR from today's harness state"
        Action   = "powershell.exe"
        Args     = "-ExecutionPolicy Bypass -WindowStyle Hidden -File `"$HarnessRoot\scripts\gemma-drift-pr.ps1`""
        Trigger  = "daily"
        Time     = "04:50"
    }
)

$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "ERROR: Must run as Administrator." -ForegroundColor Red
    Write-Host "Right-click PowerShell -> Run as administrator, then retry." -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Zuxas Harness - Task Registration" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
if ($Remove) {
    Write-Host "Removing harness scheduled tasks..." -ForegroundColor Yellow
    foreach ($task in $Tasks) {
        $existing = Get-ScheduledTask -TaskName $task.Name -ErrorAction SilentlyContinue
        if ($existing) {
            Unregister-ScheduledTask -TaskName $task.Name -Confirm:$false
            Write-Host "  [REMOVED] $($task.Name)" -ForegroundColor Green
        } else {
            Write-Host "  [SKIP] $($task.Name) - not found" -ForegroundColor Yellow
        }
    }
    Write-Host ""
    Write-Host "All harness tasks removed." -ForegroundColor Green
    exit 0
}

$okCount = 0
foreach ($task in $Tasks) {
    Write-Host "Registering: $($task.Name)..." -ForegroundColor Cyan
    Write-Host "  $($task.Desc)" -ForegroundColor Gray

    try {
        $existing = Get-ScheduledTask -TaskName $task.Name -ErrorAction SilentlyContinue
        if ($existing) {
            Unregister-ScheduledTask -TaskName $task.Name -Confirm:$false
        }

        $action = New-ScheduledTaskAction -Execute $task.Action -Argument $task.Args -WorkingDirectory $HarnessRoot

        if ($task.Trigger -eq "daily") {
            $trigger = New-ScheduledTaskTrigger -Daily -At $task.Time
        } elseif ($task.Trigger -eq "logon") {
            $trigger = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
        }

        $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -WakeToRun

        Register-ScheduledTask -TaskName $task.Name -Action $action -Trigger $trigger -Settings $settings -Description $task.Desc -Force | Out-Null

        Write-Host "  [OK] $($task.Name)" -ForegroundColor Green
        $okCount++
    } catch {
        Write-Host "  [FAIL] $($task.Name): $_" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Results: $okCount/$($Tasks.Count) tasks registered" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
if ($okCount -eq $Tasks.Count) {
    Write-Host "All automation layers LIVE." -ForegroundColor Green
    Write-Host ""
    Write-Host "SCHEDULE (early-morning handoff)" -ForegroundColor Cyan
    Write-Host "  4:30 AM daily  -> Session snapshot + drift detect + lint + drift route" -ForegroundColor White
    Write-Host "  4:50 AM daily  -> Gemma drift PR generation (Tier 3)" -ForegroundColor White
    Write-Host "  5:30 PM daily  -> Nightly harness (Modern)  [needs 5pm scraper data]" -ForegroundColor White
    Write-Host "  6:30 PM daily  -> Nightly harness (Standard) [needs 5pm scraper data]" -ForegroundColor White
    Write-Host "  On login       -> Inbox watcher (auto-compile)" -ForegroundColor White
    Write-Host "  On login       -> Session snapshot backstop (if last snapshot >12h old)" -ForegroundColor White
    Write-Host ""
    Write-Host "EXISTING (meta-analyzer):" -ForegroundColor Cyan
    Write-Host "  6:00 AM daily  -> Background fill (all formats)" -ForegroundColor White
    Write-Host "  5:00 PM daily  -> Daily scraper (Standard)" -ForegroundColor White
    Write-Host "  Sun midnight   -> Scryfall refresh" -ForegroundColor White
    Write-Host ""
    Write-Host "FLOW: scraper 5PM -> nightly 5:30PM -> [overnight] -> snapshot 4:30AM -> Gemma 4:50AM" -ForegroundColor Yellow
    Write-Host "      morning session reads latest-snapshot.md AND inbox/drift-pr--<date>.md" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "NOTE: -WakeToRun is enabled -- if PC is asleep at 4:30/4:50, it will wake to" -ForegroundColor Gray
    Write-Host "      run the task. If PC is fully off, the on-login backstop catches up." -ForegroundColor Gray
} else {
    Write-Host "Some tasks failed. Check errors above." -ForegroundColor Yellow
}
