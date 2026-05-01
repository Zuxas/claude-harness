# ask-gemma.ps1
# Quick query tool for Gemma 4 via Ollama API
# Returns answer to stdout -- no file writing, no formatting
#
# USAGE:
#   .\ask-gemma.ps1 "What is the MoE architecture?"
#   .\ask-gemma.ps1 "Summarize this" -Context (Get-Content notes.txt -Raw)
#   .\ask-gemma.ps1 "What does this do?" -ContextFile "script.ps1"
#   .\ask-gemma.ps1 "Quick question" -Model "gemma4:26b"

param(
    [Parameter(Mandatory=$true, Position=0)]
    [string]$Question,
    [string]$Context,
    [string]$ContextFile,
    [string]$Model = "gemma4"
)

$OllamaAPI = "http://localhost:11434/api/generate"

# Build prompt
$Prompt = $Question
if ($ContextFile -and (Test-Path $ContextFile)) {
    $FileContent = Get-Content $ContextFile -Raw
    $Prompt = "Context:`n$FileContent`n`nQuestion: $Question"
} elseif ($Context) {
    $Prompt = "Context:`n$Context`n`nQuestion: $Question"
}

Write-Host "[gemma] Asking $Model... " -ForegroundColor Cyan -NoNewline

$Body = @{
    model  = $Model
    prompt = $Prompt
    system = "Answer concisely and accurately. No preamble."
    stream = $false
    options = @{
        temperature = 0.4
        num_predict = 2048
    }
} | ConvertTo-Json -Depth 3

try {
    $Response = Invoke-RestMethod -Uri $OllamaAPI -Method POST -Body $Body -ContentType "application/json" -TimeoutSec 300
} catch {
    Write-Error "Ollama API failed. Is Ollama running?"
    exit 1
}

$Duration = [math]::Round($Response.total_duration / 1000000000, 1)
$Tokens = $Response.eval_count
Write-Host "done (${Tokens} tokens, ${Duration}s)" -ForegroundColor Green
Write-Host ""
Write-Host $Response.response
