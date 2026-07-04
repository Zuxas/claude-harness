---
title: "Infrastructure"
domain: "tech"
last_updated: "2026-07-03"
confidence: "high"
sources: ["conversation-history", "desktop-commander-config"]
---

## Summary
Primary development machine specs, tools, and configuration.

## Hardware
- **CPU**: AMD Ryzen 3900XT (24 threads)
- **GPU**: NVIDIA RTX 3080 LHR (10GB VRAM)
- **OS**: Windows (win32)
- **Rust**: v1.94.1 (installed)
- **External Drives**: D:, G:, H: for media library
- **Mouse**: Shopping for Razer Naga V2 HyperSpeed (replacing Corsair Scimitar)

## GPU Notes
The 3080 LHR has 10GB VRAM. Two model families are installed (verified 2026-07-03 via `ollama list`):

Code / APL generation -- qwen2.5-coder (code-specialized):
- qwen2.5-coder:7b (4.7GB): fits in VRAM, fast; the default code-gen model (auto_pipeline, ralph adapters)
- qwen2.5-coder:14b (9.0GB): higher quality, near-full VRAM fit; for harder APL passes

Prose / knowledge / LLM-judge -- gemma4 (general-purpose):
- gemma4 / gemma4:latest (9.6GB): fits in VRAM with offload, partial GPU acceleration; default for ask-gemma, compile-knowledge, process-inbox, the drift PR, and the APL judge
- gemma4:26b (MoE, 18GB file): too large for 10GB VRAM, runs hybrid CPU+GPU. Ollama automatically offloads layers that don't fit -- GPU handles what it can, CPU handles the rest. Expect ~2-4x speedup over pure CPU.

Split rationale: qwen2.5-coder is code-specialized and produces more reliable structured Python (APLs); gemma4 is the general model for prose and judging. Scripts that call `gemma4` are CORRECT for their prose/judge role -- do NOT rename them to qwen. (The prior `gemma4:e4b` 4B entry was removed -- not currently installed.)

## Development Stack
- **Python**: 3.13.12 (system install)
- **Node.js**: 24.14.0
- **Shell**: PowerShell (default)
- **IDE**: VS Code
- **Claude Code**: v2.1.109, Opus 4.6, Claude Max (1M context)
- **Desktop Commander**: v0.2.38, 115+ sessions, 10K+ tool calls
- **Filesystem MCP**: Allowed directory: `E:\vscode ai project`

## Key Patterns
- PowerShell scripts: write to `C:\temp\`, execute with `-ExecutionPolicy Bypass`
- ASCII-only output to avoid encoding errors
- Claude Code permissions extensively configured (see `.claude/settings.local.json`)
- User home: `C:\Users\jerme`

## Media Library Infrastructure
- **Tool**: yt-dlp via PowerShell scripts
- **Organization**: Per-drive, per-channel structure
- **Auth**: Cookie authentication via exported cookies.txt
- **Archive**: Archive management across drives
- **Purpose**: Offline media for deployment with no internet access
- Scripts are highly evolved (v6-v8+), consolidated channel list

## MCP Integrations
- Desktop Commander (active, heavily used)
- Filesystem (active, E:\vscode ai project)
- Google Drive (authorized but recurring session-loading issues)
- Claude in Chrome (available)
- PDF Tools (available)
- Figma (available)

## Harness Components (installed stack)
- [x] Obsidian v1.12.7 — knowledge base viewer
- [x] Ollama v0.20.7 — local model runner
- [x] qwen2.5-coder:7b (4.7GB) — code/APL generation (default codegen)
- [x] qwen2.5-coder:14b (9.0GB) — higher-quality codegen
- [x] gemma4 / gemma4:latest (9.6GB) — prose/knowledge/judge (default)
- [x] gemma4:26b MoE (18GB) — high-quality prose (hybrid CPU+GPU)
- [x] Rust v1.94.1 — installed
- [ ] VS Build Tools — installing (needed for RTK compilation)
- [ ] RTK — blocked on VS Build Tools, then `cargo install`
- [ ] botctl — autonomous agent process manager (future)

## Twitch
- Handle: zuxasLOL
- Content: World-first raiding, 3k+ Mythic+ keys, Summoners War, MTG

## Changelog
- 2026-04-14: Created from Claude memory + Desktop Commander config
- 2026-04-14: Added GPU (RTX 3080 LHR 10GB), updated Claude Code version,
  marked Obsidian/Ollama/Gemma4/Rust as installed, added VRAM sizing notes
- 2026-07-03: Reconciled Ollama model inventory to actual installed set --
  qwen2.5-coder 7b/14b (code/APL) + gemma4 latest/26b (prose/judge). Removed
  phantom gemma4:e4b. Documented the code-vs-prose model split. (Naming-drift
  reconciliation pass; scripts calling gemma4 for prose left as-is, correct.)
