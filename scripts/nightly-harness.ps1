# nightly-harness.ps1
# PowerShell wrapper for the nightly harness job
#
# USAGE:
#   .\nightly-harness.ps1                          # full run (modern)
#   .\nightly-harness.ps1 -Format standard         # specific format
#   .\nightly-harness.ps1 -DryRun                  # show what would happen
#   .\nightly-harness.ps1 -SkipMTGA                # skip MTGA log parsing
#   .\nightly-harness.ps1 -EnableAutoPipeline      # opt into Layer 5 auto_pipeline (default Gemma)
#   .\nightly-harness.ps1 -EnableAutoPipeline -AutoPipelineUseClaude  # both flags = Claude path
#
# To enable in scheduled task: edit the task command line to add
# '-EnableAutoPipeline'. Spec: harness/specs/2026-04-28-auto-pipeline-
# nightly-integration.md (default off for Friday safety).

param(
    [string]$Format = "modern",
    [switch]$DryRun,
    [switch]$SkipMTGA,
    [switch]$EnableAutoPipeline,
    [switch]$AutoPipelineUseClaude
)

$Script = "E:\vscode ai project\harness\agents\scripts\nightly_harness.py"
$args_list = @("--format", $Format)
if ($DryRun)                 { $args_list += "--dry-run" }
if ($SkipMTGA)               { $args_list += "--skip-mtga" }
if ($EnableAutoPipeline)     { $args_list += "--enable-auto-pipeline" }
if ($AutoPipelineUseClaude)  { $args_list += "--auto-pipeline-use-claude" }

python $Script @args_list
