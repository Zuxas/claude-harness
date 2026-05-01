# ============================================================
#  ZUXAS HARNESS — QUICK REFERENCE
#  Open PowerShell, paste these commands
# ============================================================

# FIRST: Navigate to your scripts folder
cd "E:\vscode ai project\harness\scripts"

# ============================================================
#  GRIND ONE DECK (runs Gemma locally, $0.00)
# ============================================================
.\grind-apl.ps1 "Amulet Titan" -Target 5.0
.\grind-apl.ps1 "Boros Energy" -Target 4.5
.\grind-apl.ps1 "Izzet Prowess" -Target 4.5
.\grind-apl.ps1 "Dimir Murktide" -Target 5.5

# With options:
.\grind-apl.ps1 "Amulet Titan" -Target 5.0 -MaxIter 15   # more iterations
.\grind-apl.ps1 "Amulet Titan" -Target 5.0 -Games 2000    # more games per test
.\grind-apl.ps1 "Amulet Titan" -Target 5.0 -Model gpt4o   # use GPT-4o (needs billing)
.\grind-apl.ps1 "Amulet Titan" -AnalyzeLogs               # just show fast vs slow games

# ============================================================
#  GRIND ALL DECKS (runs through every Modern deck)
# ============================================================
.\grind-all.ps1

# ============================================================
#  APL OPTIMIZER (card-level: find missing cards, patch logic)
# ============================================================
.\optimize-apl.ps1 "Boros Energy"
.\optimize-apl.ps1 "Amulet Titan" -Iterations 3

# ============================================================
#  TUNE LOOP (swap cards in/out, test vs field)
# ============================================================
.\tune-loop.ps1 "Boros Energy"
.\tune-loop.ps1 "Jeskai Blink"

# ============================================================
#  OTHER TOOLS
# ============================================================
.\stress-test.ps1                    # health check (all systems)
.\compile-knowledge.ps1              # rebuild knowledge base
.\kb-status.ps1                      # show knowledge block status
.\ask-gemma.ps1 "your question"      # ask Gemma anything
.\calibrate.ps1                      # compare sim vs real match results
.\parse-mtga.ps1                     # parse Arena game logs
.\watch-inbox.ps1                    # start inbox file watcher

# ============================================================
#  CHECK RESULTS
# ============================================================
# See grind reports:
Get-Content "E:\vscode ai project\harness\knowledge\mtg\grind-amulet-titan-2026-04-18.md"

# List all reports:
dir "E:\vscode ai project\harness\knowledge\mtg\grind-*"

# See if improved APL was saved:
dir "E:\vscode ai project\mtg-sim\apl\*grind*"

# Apply a grind result permanently:
# copy "E:\vscode ai project\mtg-sim\apl\amulet_titan_grind_2026-04-18.py" "E:\vscode ai project\mtg-sim\apl\amulet_titan.py"

# Quick sim test (from mtg-sim folder):
cd "E:\vscode ai project\mtg-sim"
python -c "from data.deck import load_deck_from_file; from apl.boros_energy import BorosEnergyAPL; from engine.runner import run_simulation; m,s=load_deck_from_file('decks/boros_energy_modern.txt'); r=run_simulation(BorosEnergyAPL(),m,n=1000); print(f'T{r.avg_kill_turn():.2f} avg | {r.win_rate():.1%} WR')"
