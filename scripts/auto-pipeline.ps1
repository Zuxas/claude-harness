# auto-pipeline.ps1
# Layer 5: Full Pipeline Automation wrapper
#
# USAGE:
#   .\auto-pipeline.ps1                                   # full pipeline (modern, Claude API)
#   .\auto-pipeline.ps1 -Format standard                  # standard format
#   .\auto-pipeline.ps1 -UseGemma                         # free APL generation (lower quality)
#   .\auto-pipeline.ps1 -DryRun                           # show plan only
#   .\auto-pipeline.ps1 -GenerateAPL "New Deck Name"      # generate one APL
#   .\auto-pipeline.ps1 -DraftPlaybook "Boros Energy"     # draft one playbook
#   .\auto-pipeline.ps1 -ShowMemory                       # view experiment history

param(
    [string]$Format = "modern",
    [switch]$DryRun,
    [switch]$UseGemma,
    [string]$GenerateAPL,
    [string]$DraftPlaybook,
    [switch]$ShowMemory
)

$Script = "E:\vscode ai project\harness\agents\scripts\auto_pipeline.py"
$args_list = @("--format", $Format)
if ($DryRun)         { $args_list += "--dry-run" }
if ($UseGemma)       { $args_list += "--use-gemma" }
if ($GenerateAPL)    { $args_list += "--generate-apl"; $args_list += $GenerateAPL }
if ($DraftPlaybook)  { $args_list += "--draft-playbook"; $args_list += $DraftPlaybook }
if ($ShowMemory)     { $args_list += "--show-memory" }

python $Script @args_list
