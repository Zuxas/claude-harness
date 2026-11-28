# calibrate.ps1
# Layer 4: Sim Calibration - compare real match results vs sim predictions
#
# USAGE:
#   .\calibrate.ps1                              # all matches
#   .\calibrate.ps1 -Deck "Dimir Tempo"          # specific deck
#   .\calibrate.ps1 -Format standard             # specific format
#   .\calibrate.ps1 -MinMatches 3                # require 3+ matches
#   .\calibrate.ps1 -DryRun                      # show data only

param(
    [string]$Deck,
    [string]$Format,
    [int]$MinMatches = 1,
    [int]$Games = 500,
    [switch]$DryRun
)

# Resolve roots (env override or derive from location); see _roots.ps1 (#51).
. "$PSScriptRoot\_roots.ps1"

$Script = "$AgentScripts\calibrate.py"
$args_list = @()
if ($Deck)       { $args_list += "--deck"; $args_list += $Deck }
if ($Format)     { $args_list += "--format"; $args_list += $Format }
$args_list += "--min-matches"; $args_list += $MinMatches
$args_list += "--games"; $args_list += $Games
if ($DryRun)     { $args_list += "--dry-run" }

python $Script @args_list
