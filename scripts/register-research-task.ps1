# ENCODING NOTE: ASCII-only. This file must contain only 7-bit ASCII bytes.
#
# register-research-task.ps1
# Builds (and optionally registers) the Windows Task Scheduler entry for the
# SP-4 research-ingest loop: a DAILY 05:10 task that runs the ingest script
# and then the nightly digest. LOCAL-ONLY; no network, no cloud LLM vendor.
#
# DEFAULT BEHAVIOR: dry-run. The script PRINTS what it would register and
# does NOT execute it. Pass -Execute to actually register the task.
#
# USAGE:
#   .\register-research-task.ps1            # dry-run: print only
#   .\register-research-task.ps1 -Execute   # actually register the task
#
# IMPLEMENTATION NOTE (2026-07-04): registration uses the native
# ScheduledTasks cmdlets (New-ScheduledTaskAction/Trigger/Principal +
# Register-ScheduledTask) rather than a schtasks.exe /TR string. The old
# schtasks approach mangled the nested `-Command "..."` quotes when splatted
# to the native exe (schtasks saw '-ExecutionPolicy' as its own arg and
# failed 0x80004005). The action now points at a single launcher script
# (run-research-nightly.ps1), so the argument is one clean `-File <path>`.
#
# /RL LIMITED is preserved via -RunLevel Limited (least-privilege; no admin
# needed). WakeToRun is NOT set; to wake the PC from sleep for this slot:
#   schtasks /Change /TN "Zuxas-Harness-ResearchIngest" /WakeToRun

param(
    [switch]$Execute
)

$ErrorActionPreference = "Stop"

$Root      = "E:\vscode ai project"
$TaskName  = "Zuxas-Harness-ResearchIngest"
$Time      = "05:10"
$Launcher  = "$Root\harness\scripts\run-research-nightly.ps1"

# The scheduled action is a single clean -File invocation of the launcher,
# which itself runs ingest then digest. No nested quotes.
$PsArgs = "-ExecutionPolicy Bypass -File `"$Launcher`""

Write-Output "ENCODING NOTE: ASCII-only."
Write-Output ""
Write-Output "Task name : $TaskName"
Write-Output "Schedule  : DAILY at $Time"
Write-Output "Run level : LIMITED (-RunLevel Limited)"
Write-Output "Action    : powershell.exe $PsArgs"
Write-Output "Launcher  : $Launcher (runs ingest-research.ps1 then research_digest.py)"
Write-Output ""
Write-Output "WakeToRun note: not set. To wake the PC from sleep for this slot:"
Write-Output "  schtasks /Change /TN `"$TaskName`" /WakeToRun"

if ($Execute) {
    Write-Output ""
    Write-Output "-Execute supplied: registering the task now..."

    $action    = New-ScheduledTaskAction -Execute "powershell.exe" -Argument $PsArgs
    $trigger   = New-ScheduledTaskTrigger -Daily -At $Time
    $principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
    $settings  = New-ScheduledTaskSettingsSet -StartWhenAvailable

    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger `
        -Principal $principal -Settings $settings `
        -Description "SP-4 research-ingest loop: ingest then digest, DAILY 05:10, LOCAL-ONLY." `
        -Force | Out-Null

    $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if ($t) {
        $info = Get-ScheduledTaskInfo -TaskName $TaskName
        Write-Output "REGISTERED: $TaskName state=$($t.State) nextRun=$($info.NextRunTime)"
        exit 0
    } else {
        Write-Output "ERROR: registration did not produce a task."
        exit 1
    }
} else {
    Write-Output ""
    Write-Output "DRY-RUN: task NOT registered. Re-run with -Execute to register."
    exit 0
}
