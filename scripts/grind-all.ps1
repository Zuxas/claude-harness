# grind-all.ps1 -- Run the grinder on all Modern decks
# Supports --Until for time-based grinding
#
# USAGE:
#   .\grind-all.ps1                        # 10 iterations per deck
#   .\grind-all.ps1 -Until "8:00"          # grind all decks until 8:00 AM
#   .\grind-all.ps1 -Until "23:00"         # grind until 11 PM
#   .\grind-all.ps1 -Model gpt4o           # use GPT-4o

param(
    [int]$MaxIter = 10,
    [int]$Games = 500,
    [string]$Model = "gemma4",
    [string]$Until = "",
    [int]$Duration = 0
)

$env:OPENAI_API_KEY = [Environment]::GetEnvironmentVariable("OPENAI_API_KEY", "User")
$env:GEMINI_API_KEY = [Environment]::GetEnvironmentVariable("GEMINI_API_KEY", "User")

$Script = "E:\vscode ai project\harness\agents\scripts\apl_grinder.py"

$Decks = @(
    @{Name="Boros Energy"; Target=4.5},
    @{Name="Izzet Prowess"; Target=4.5},
    @{Name="Amulet Titan"; Target=5.0},
    @{Name="Dimir Murktide"; Target=6.5},
    @{Name="Eldrazi Ramp"; Target=5.5},
    @{Name="Domain Zoo"; Target=5.0},
    @{Name="Mono Red Aggro"; Target=4.0},
    @{Name="Esper Blink"; Target=6.5},
    @{Name="Jeskai Blink"; Target=6.5}
)

# Compute the absolute stop time ONCE, before the loop.
# Recomputing it per deck and rolling a past time to "tomorrow" is what made
# the overnight grind never stop, and passing the same wall-clock --until to
# every grinder call let the first deck eat the whole window (issue #12).
$stopDT = $null
if ($Duration -gt 0) {
    $stopDT = (Get-Date).AddMinutes($Duration)
    Write-Host "  Duration: $Duration minutes (until $($stopDT.ToString('HH:mm')))"
} elseif ($Until) {
    $parts = $Until -split ":"
    $stopHour = [int]$parts[0]
    $stopMin  = if ($parts.Count -gt 1) { [int]$parts[1] } else { 0 }
    $stopDT = (Get-Date).Date.AddHours($stopHour).AddMinutes($stopMin)
    if ($stopDT -lt (Get-Date)) { $stopDT = $stopDT.AddDays(1) }  # roll forward ONCE
}
$timed = $null -ne $stopDT

$StopDisplay = if ($timed) { "Until $($stopDT.ToString('yyyy-MM-dd HH:mm'))" } else { "$MaxIter iterations/deck" }
$StartTime = Get-Date
Write-Host ""
Write-Host "============================================"
Write-Host "  GRIND ALL MODERN DECKS"
Write-Host "  Decks: $($Decks.Count) | Model: $Model"
Write-Host "  Mode: $StopDisplay"
Write-Host "============================================"

# Loop through decks, cycling back to start if time remains
$round = 0
$totalImproved = 0
$keepGoing = $true

while ($keepGoing) {
    $round++
    Write-Host ""
    Write-Host "=== ROUND $round ==="
    
    for ($di = 0; $di -lt $Decks.Count; $di++) {
        $deck = $Decks[$di]
        # Time check + per-deck budget
        $deckBudget = 0
        if ($timed) {
            $remaining = ($stopDT - (Get-Date)).TotalMinutes
            if ($remaining -le 0) {
                Write-Host "  STOP TIME REACHED"
                $keepGoing = $false
                break
            }
            # Split the remaining window across the decks still to run this round,
            # so one deck can't consume the whole window. Decks that converge early
            # return their unused time to the ones after them.
            $decksLeft = $Decks.Count - $di
            $deckBudget = [math]::Max(1, [math]::Ceiling($remaining / $decksLeft))
            Write-Host "  [$([math]::Round($remaining)) min remaining; this deck <= $deckBudget min]"
        }

        $name = $deck.Name
        $target = $deck.Target
        Write-Host ""
        Write-Host "--- $name (target T$target) ---"

        $argsList = @($name, "--target", $target, "--max-iterations", $MaxIter, "--games", $Games, "--model", $Model)
        if ($timed) { $argsList += @("--duration", $deckBudget) }  # minutes, not wall-clock --until

        python $Script @argsList
        
        # Auto-apply improvements
        $safe = $name.ToLower().Replace(" ", "_")
        $today = Get-Date -Format "yyyy-MM-dd"
        $grindFile = Get-ChildItem "E:\vscode ai project\mtg-sim\apl" -Filter "${safe}_grind_${today}*" -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1
        if ($grindFile) {
            Copy-Item $grindFile.FullName "E:\vscode ai project\mtg-sim\apl\${safe}.py" -Force
            Write-Host "  APPLIED: $($grindFile.Name)"
            $totalImproved++
        }
    }
    
    # If not time-based, stop after one round
    if (-not $timed) { $keepGoing = $false }
}

$TotalMin = [math]::Round(((Get-Date) - $StartTime).TotalMinutes, 1)
Write-Host ""
Write-Host "============================================"
Write-Host "  GRIND ALL COMPLETE"
Write-Host "  Rounds: $round | Improved: $totalImproved"  
Write-Host "  Total time: $TotalMin minutes"
Write-Host "============================================"
