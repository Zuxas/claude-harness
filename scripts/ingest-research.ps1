# ENCODING NOTE: ASCII-only (PowerShell 5.1 parses this file)
#
# ingest-research.ps1 == wrapper for the research-ingest lane.
# Resolves the repo root relative to this script and invokes the Python
# ingester, passing through any arguments.

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$root = Split-Path -Parent (Split-Path -Parent $scriptDir)
$py = Join-Path $root "harness\agents\scripts\ingest_research.py"

python $py $args
exit $LASTEXITCODE
