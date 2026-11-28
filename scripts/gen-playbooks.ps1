# gen-playbooks.ps1 -- Generate playbook HTML from sim data
# Usage:
#   .\gen-playbooks.ps1 -Format modern -All
#   .\gen-playbooks.ps1 -Deck "Boros Energy" -Format modern
#   .\gen-playbooks.ps1 -Format modern -All -DryRun

param(
    [string]$Format = "modern",
    [string]$Deck = "",
    [switch]$All,
    [switch]$DryRun
)

# Resolve roots (env override or derive from location); see _roots.ps1 (#51).
. "$PSScriptRoot\_roots.ps1"

$script = "$AgentScripts\playbook_generator.py"
$args_list = @("--format", $Format)

if ($All) { $args_list += "--all" }
if ($Deck) { $args_list += $Deck }
if ($DryRun) { $args_list += "--dry-run" }

Push-Location "$ProjectRoot"
python $script @args_list
Pop-Location
