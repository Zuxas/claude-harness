# optimize-apl.ps1
# APL Self-Tuner - reads APL code, finds logic holes, patches and tests
#
# USAGE:
#   .\optimize-apl.ps1 "Boros Energy"                                   # gemma4 (free, fast)
#   .\optimize-apl.ps1 "Boros Energy" -Model "qwen3-coder:30b"          # code specialist (free, slower)
#   .\optimize-apl.ps1 "Boros Energy" -Model "deepseek-v3.1:671b-cloud" # cloud 671B (free, best quality)
#   .\optimize-apl.ps1 "Boros Energy" -Model "qwen3.5:397b-cloud"       # cloud 397B (free)
#   .\optimize-apl.ps1 "Boros Energy" -UseClaude                        # Claude API (~$0.05)
#   .\optimize-apl.ps1 "Jeskai Blink" -AnalyzeOnly                     # analysis only
#   .\optimize-apl.ps1 "Esper Blink" -Iterations 3                     # more passes

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$Deck,
    [string]$Format = "modern",
    [int]$Games = 500,
    [int]$Iterations = 2,
    [string]$Model = "gemma4",
    [switch]$AnalyzeOnly,
    [switch]$UseClaude
)

$Script = "E:\vscode ai project\harness\agents\scripts\apl_optimizer.py"
$args_list = @($Deck, "--format", $Format, "--games", $Games, "--iterations", $Iterations, "--model", $Model)
if ($AnalyzeOnly) { $args_list += "--analyze-only" }
if ($UseClaude)   { $args_list += "--use-claude" }

python $Script @args_list
