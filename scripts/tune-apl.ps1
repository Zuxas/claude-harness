# tune-apl.ps1
# PowerShell wrapper for the APL Tuner Agent
#
# USAGE:
#   .\tune-apl.ps1 "Boros Energy"                    (analyze mode)
#   .\tune-apl.ps1 "Humans" -Mode full -Format legacy
#   .\tune-apl.ps1 "Izzet Prowess" -Mode validate
#   .\tune-apl.ps1 -ListAPLs
#   .\tune-apl.ps1 -ListDecks -Format modern

param(
    [Parameter(Position=0)]
    [string]$Deck,
    [ValidateSet("validate","analyze","full")]
    [string]$Mode = "analyze",
    [string]$Format = "modern",
    [int]$Games = 1000,
    [switch]$ListAPLs,
    [switch]$ListDecks
)

$Script = "E:\vscode ai project\harness\agents\scripts\apl_tuner.py"

if ($ListAPLs) {
    python $Script --list-apls
} elseif ($ListDecks) {
    python $Script --list-decks --format $Format
} elseif ($Deck) {
    python $Script $Deck --mode $Mode --format $Format --games $Games
} else {
    Write-Host "USAGE: .\tune-apl.ps1 'Deck Name' [-Mode validate|analyze|full] [-Format modern] [-Games 1000]"
    Write-Host ""
    Write-Host "EXAMPLES:"
    Write-Host "  .\tune-apl.ps1 'Boros Energy'                    # analyze goldfish + Gemma"
    Write-Host "  .\tune-apl.ps1 'Humans' -Mode full -Format legacy # full gauntlet + analysis"
    Write-Host "  .\tune-apl.ps1 -ListAPLs                         # show all APLs"
    Write-Host "  .\tune-apl.ps1 -ListDecks -Format modern          # show all decks"
}
