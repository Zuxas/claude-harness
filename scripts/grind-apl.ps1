# grind-apl.ps1
# APL Grinder - iterative refinement until target kill turn or stop time
#
# USAGE:
#   .\grind-apl.ps1 "Amulet Titan" -Target 5.0                    # 10 iterations
#   .\grind-apl.ps1 "Amulet Titan" -Target 5.0 -MaxIter 50        # 50 iterations
#   .\grind-apl.ps1 "Amulet Titan" -Target 5.0 -Duration 30     # run for 30 minutes
#   .\grind-apl.ps1 "Amulet Titan" -Target 5.0 -Until "8:00"      # run until 8:00 AM
#   .\grind-apl.ps1 "Amulet Titan" -Target 5.0 -Until "23:30"     # run until 11:30 PM
#   .\grind-apl.ps1 "Boros Energy" -Target 4.5 -Model gpt4o
#   .\grind-apl.ps1 "Amulet Titan" -AnalyzeLogs

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$Deck,
    [float]$Target = 5.0,
    [int]$MaxIter = 10,
    [int]$Games = 500,
    [string]$Model = "gemma4",
    [string]$Until = "",
    [int]$Duration = 0,
    [switch]$AnalyzeLogs
)

$env:OPENAI_API_KEY = [Environment]::GetEnvironmentVariable("OPENAI_API_KEY", "User")
$env:GEMINI_API_KEY = [Environment]::GetEnvironmentVariable("GEMINI_API_KEY", "User")

$Script = "E:\vscode ai project\harness\agents\scripts\apl_grinder.py"
$args_list = @($Deck, "--target", $Target, "--max-iterations", $MaxIter, "--games", $Games, "--model", $Model)
if ($Until) { $args_list += @("--until", $Until) }
if ($Duration -gt 0) { $args_list += @("--duration", $Duration) }
if ($AnalyzeLogs) { $args_list += "--analyze-logs" }

python $Script @args_list
