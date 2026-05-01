# verify-oracle.ps1 -- Oracle text vs APL implementation checker
# Wrapper around harness/scripts/verify_oracle.py
#
# Usage:
#   .\verify-oracle.ps1 "Lava Dart" mtg-sim\apl\izzet_prowess_match.py
#   .\verify-oracle.ps1 --batch mtg-sim\apl\boros_energy.py
#
# Exit 0 = PASS, Exit 1 = FAIL (discrepancies found), Exit 2 = error

param(
    [Parameter(Position=0)] [string]$CardOrFlag,
    [Parameter(Position=1)] [string]$AplFile
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonScript = Join-Path $ScriptDir "verify_oracle.py"

if ($CardOrFlag -eq "--batch") {
    python $PythonScript --batch $AplFile
} else {
    python $PythonScript $CardOrFlag $AplFile
}

exit $LASTEXITCODE
