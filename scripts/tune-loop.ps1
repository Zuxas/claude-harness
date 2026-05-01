# tune-loop.ps1
# Layer 3: Autonomous Tuning Loop wrapper
#
# USAGE:
#   .\tune-loop.ps1 "Boros Energy"                           # 3 iterations, modern
#   .\tune-loop.ps1 "Humans" -Format legacy -Iterations 5    # legacy, 5 iterations
#   .\tune-loop.ps1 "Boros Energy" -DryRun                   # show plan only
#   .\tune-loop.ps1 "Izzet Prowess" -Games 1000              # more games = more accurate

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$Deck,
    [string]$Format = "modern",
    [int]$Iterations = 3,
    [int]$Games = 500,
    [int]$FieldSize = 8,
    [switch]$DryRun
)

$Script = "E:\vscode ai project\harness\agents\scripts\tuning_loop.py"
$args_list = @($Deck, "--format", $Format, "--iterations", $Iterations, "--games", $Games, "--field-size", $FieldSize)
if ($DryRun) { $args_list += "--dry-run" }

python $Script @args_list
