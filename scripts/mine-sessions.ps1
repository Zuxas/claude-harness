# ENCODING NOTE: ASCII-only
# SP-5 session-mining loop wrapper. Resolves repo root, calls the Python
# miner, passes through all args, and exits with Python's exit code.

$ErrorActionPreference = 'Stop'

# harness/scripts/mine-sessions.ps1 -> repo root is two levels up.
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent (Split-Path -Parent $scriptDir)
$py = Join-Path $root 'harness\agents\scripts\mine_sessions.py'

& python $py @args
exit $LASTEXITCODE
