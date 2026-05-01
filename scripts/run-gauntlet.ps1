# run-gauntlet.ps1 -- Run matchup gauntlet via match engine
# Usage:
#   .\run-gauntlet.ps1 -Format modern -Games 500
#   .\run-gauntlet.ps1 -Format modern -Top 8 -DryRun
#   .\run-gauntlet.ps1 -Format standard -Deck "Izzet Prowess"

param(
    [string]$Format = "modern",
    [int]$Games = 500,
    [int]$Top = 0,
    [string]$Deck = "",
    [switch]$DryRun
)

$script = "E:\vscode ai project\harness\agents\scripts\matchup_gauntlet.py"
$args_list = @("--format", $Format, "--games", $Games)

if ($Top -gt 0) { $args_list += @("--top", $Top) }
if ($Deck) { $args_list += @("--deck", $Deck) }
if ($DryRun) { $args_list += "--dry-run" }

Push-Location "E:\vscode ai project"
python $script @args_list
Pop-Location
