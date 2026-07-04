# start-llamacpp-tier2.ps1 — launch the tier-2 local LLM (Qwen3-Coder-30B-A3B)
# Spec: harness/specs/2026-07-03-local-llm-delegation.md (EXECUTING), Phase 1 Step 4.
#
# Tier-2 = MoE expert-offload to 64GB RAM via llama.cpp. Attention+KV stay on the
# 10GB GPU (-ngl 999), expert weights spill to RAM (--n-cpu-moe). Persistent server
# on :8080 exposing an OpenAI-compatible /v1/chat/completions endpoint.
#
# one_tier_hot: the 10GB 3080 can't hold tier-1 (ollama 7B ~7GB) AND tier-2 at once,
# so this script stops loaded Ollama models first to free VRAM. Swaps are cheap
# (warm page cache in 64GB). Run:  powershell -ExecutionPolicy Bypass -File this.ps1

param(
    [string]$Model  = "E:\models\Qwen3-Coder-30B-A3B-Instruct-Q4_K_M.gguf",
    [int]$Port      = 8080,
    [int]$NCpuMoe   = 32,        # experts offloaded to RAM; lower = more on GPU (faster) if VRAM allows
    [int]$Ctx       = 32768,
    [switch]$KeepOllama,         # pass to SKIP unloading Ollama (only if you've proven co-residency)
    [switch]$Stop                # stop the tier-2 server (by PATH, so Ollama's engine is untouched)
)

$ErrorActionPreference = "Stop"
$LlamaServer = "E:\tools\llama.cpp\llama-server.exe"

if ($Stop) {
    # Ollama's internal engine is ALSO llama-server.exe — match by PATH only.
    $procs = Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'" |
             Where-Object { $_.ExecutablePath -like 'E:\tools\llama.cpp\*' }
    if ($procs) {
        $procs | ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Host "stopped tier-2 PID $($_.ProcessId)" }
    } else { Write-Host "no tier-2 llama-server running" }
    return
}

if (-not (Test-Path $LlamaServer)) { throw "llama-server.exe not found at $LlamaServer" }
if (-not (Test-Path $Model))       { throw "GGUF not found at $Model (still downloading?)" }

# one_tier_hot: free VRAM by stopping any loaded Ollama models (unless -KeepOllama)
if (-not $KeepOllama) {
    Write-Host "[one_tier_hot] stopping loaded Ollama models to free VRAM..."
    try {
        $ps = & ollama ps 2>$null | Select-Object -Skip 1
        foreach ($line in $ps) {
            $name = ($line -split '\s+')[0]
            if ($name) { & ollama stop $name 2>$null; Write-Host "  stopped $name" }
        }
    } catch { Write-Host "  (ollama not running or nothing to stop)" }
}

# NOTE: Ollama's OWN internal engine is also named llama-server.exe
# (C:\...\Ollama\lib\ollama\llama-server.exe). To STOP tier-2, target by PATH,
# never by process name, or you'll kill Ollama's engine too:
#   Get-CimInstance Win32_Process -Filter "Name='llama-server.exe'" |
#     Where-Object { $_.ExecutablePath -like 'E:\tools\llama.cpp\*' } |
#     ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
#
# Tuning from the first live run (2026-07-03, 20 tok/s @ n-cpu-moe 32):
#   --parallel 1  : one KV slot instead of the default 4 (default ballooned VRAM
#                   to 9.8/10GB via 4x KV). Frees headroom; matches OLLAMA_NUM_PARALLEL=1.
#   --no-mmap     : load weights fully into the 64GB RAM (the loader warns mmap +
#                   CPU expert-offload is slower). Costs a slower cold load, buys tok/s.
# With --parallel 1 freeing VRAM, a future tune can LOWER --n-cpu-moe (more experts
# on GPU = faster) — re-benchmark before committing (Gate 5.1 / P5).
Write-Host "[tier-2] launching Qwen3-Coder-30B-A3B on :$Port (n-cpu-moe=$NCpuMoe, ctx=$Ctx, parallel=1)..."
& $LlamaServer `
    -m $Model `
    -ngl 999 `
    --n-cpu-moe $NCpuMoe `
    -fa on `
    --cache-type-k q8_0 `
    --cache-type-v q8_0 `
    -c $Ctx `
    --parallel 1 `
    --no-mmap `
    --jinja `
    --host 127.0.0.1 `
    --port $Port `
    --metrics
