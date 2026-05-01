# install-stack.ps1
# Installs the harness infrastructure stack
# Run manually — each component is independent
# Usage: powershell -ExecutionPolicy Bypass -File "E:\vscode ai project\harness\scripts\install-stack.ps1"

Write-Host "=== HARNESS STACK INSTALLER ===" -ForegroundColor Cyan
Write-Host ""

# 1. Ollama (local LLM runner)
Write-Host "[1/4] Ollama — local model runner for Gemma 4" -ForegroundColor Yellow
Write-Host "  Install: winget install Ollama.Ollama" -ForegroundColor Gray
Write-Host "  Then:    ollama pull gemma2:27b" -ForegroundColor Gray
Write-Host "  Note:    gemma4 26B MoE will be 'gemma4:26b' once available on Ollama" -ForegroundColor Gray
Write-Host ""

# 2. Rust (needed for RTK)
Write-Host "[2/4] Rust — needed to build RTK" -ForegroundColor Yellow
Write-Host "  Install: winget install Rustlang.Rustup" -ForegroundColor Gray
Write-Host "  Then:    restart terminal, run: rustup default stable" -ForegroundColor Gray
Write-Host ""

# 3. RTK (token compression for Claude Code)
Write-Host "[3/4] RTK — reduces Claude Code token consumption 60-90%" -ForegroundColor Yellow
Write-Host "  Install: cargo install --git https://github.com/rtk-ai/rtk" -ForegroundColor Gray
Write-Host "  Then:    rtk init -g" -ForegroundColor Gray
Write-Host "  Note:    Best experience in WSL. On native Windows, uses CLAUDE.md injection mode" -ForegroundColor Gray
Write-Host ""

# 4. Obsidian (knowledge base viewer)
Write-Host "[4/4] Obsidian — view knowledge blocks with graph visualization" -ForegroundColor Yellow
Write-Host "  Install: winget install Obsidian.Obsidian" -ForegroundColor Gray
Write-Host "  Then:    Open as vault -> E:\vscode ai project\harness\knowledge\" -ForegroundColor Gray
Write-Host "  Plugins: Smart Connections (for AI-powered search of your vault)" -ForegroundColor Gray
Write-Host ""

Write-Host "=== INSTALL ORDER ===" -ForegroundColor Green
Write-Host "  Priority 1: Obsidian (free, instant value — see your knowledge graph)" -ForegroundColor White
Write-Host "  Priority 2: Ollama + Gemma 4 (local model for knowledge compilation)" -ForegroundColor White
Write-Host "  Priority 3: Rust + RTK (token savings on Claude Code sessions)" -ForegroundColor White
Write-Host ""
Write-Host "Run each winget command in a separate terminal." -ForegroundColor Gray
Write-Host "=== END ===" -ForegroundColor Cyan
