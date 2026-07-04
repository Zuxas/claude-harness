# ENCODING NOTE: ASCII-only. This file must contain only 7-bit ASCII bytes.
#
# run-research-nightly.ps1
# Single launcher for the SP-4 nightly research loop. Runs the ingest step,
# then the digest step, in order. LOCAL-ONLY; no network beyond fetching
# queued URLs, no cloud LLM vendor.
#
# This exists so the scheduled task's action is one clean `-File <launcher>`
# invocation instead of a nested `-Command "..."` string (which breaks
# schtasks.exe / native-exe argument quoting on Windows PowerShell 5.1).
#
# Registered by register-research-task.ps1 as the 05:10
# Zuxas-Harness-ResearchIngest action.

# Continue so the digest still runs even if ingest reports a non-zero step
# (mirrors the original ';' sequencing intent).
$ErrorActionPreference = "Continue"

$Root      = "E:\vscode ai project"
$IngestPs1 = "$Root\harness\scripts\ingest-research.ps1"
$DigestPy  = "$Root\harness\agents\scripts\research_digest.py"

& powershell -ExecutionPolicy Bypass -File "$IngestPs1"
& python "$DigestPy"
