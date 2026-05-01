---
title: "Infrastructure"
domain: "tech"
last_updated: "2026-04-14"
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
The 3080 LHR has 10GB VRAM. For Ollama models:
- gemma4 (default 12B, 9.6GB file): fits in VRAM with offload, partial GPU acceleration
- gemma4:26b (MoE, 17GB file): too large for 10GB VRAM, runs hybrid CPU+GPU
  Ollama automatically offloads layers that don't fit — GPU handles what it can,
  CPU handles the rest. Still faster than pure CPU because the 3080 accelerates
  the layers it can hold. Expect ~2-4x speedup over pure CPU for the 26B.
- gemma4:e4b (4B, ~2.5GB): fits entirely in VRAM, fastest option for quick tasks

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
- [x] Gemma 4 default (12B) — confirmed working, 9.6GB
- [x] Gemma 4 26B MoE — pulling (17GB download)
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
