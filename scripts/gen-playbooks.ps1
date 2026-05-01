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

$script = "E:\vscode ai project\harness\agents\scripts\playbook_generator.py"
$args_list = @("--format", $Format)

if ($All) { $args_list += "--all" }
if ($Deck) { $args_list += $Deck }
if ($DryRun) { $args_list += "--dry-run" }

Push-Location "E:\vscode ai project"
python $script @args_list
Pop-Location
