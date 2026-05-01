---
title: "PowerShell Patterns"
domain: "tech"
last_updated: "2026-04-14"
confidence: "high"
sources: ["conversation-history", "yt-rip-scripts"]
---

## Summary
Jermey's PowerShell scripting conventions and the yt-dlp media library system.

## Scripting Conventions
- Write `.ps1` files to `C:\temp\` then execute:
  `powershell -ExecutionPolicy Bypass -File C:\temp\script.ps1`
- ASCII-only output — Windows terminal encoding causes issues with Unicode
- Never pass complex inline commands through bash; always use script files
- Scripts located in `E:\vscode ai project\YT-rip\`

## Media Library System
- **Purpose**: Offline media for deployment with no internet access
- **Tool**: yt-dlp (installed via WinGet)
- **Script versions**: download_artists_v8.ps1, download_abridged_v6.ps1,
  download_highrollers_v2.ps1
- **Drive layout**:
  - D: — artists/music content
  - G: — abridged series
  - H: — high rollers / campaign content

## Script Features
- Per-drive organization with channel-specific folders
- Cookie authentication via exported cookies.txt (browser export)
- Archive management (yt-dlp --download-archive) per drive
- Consolidated channel list across scripts
- Error handling and resume capability

## Common Operations
```powershell
# Execute a temp script
powershell -ExecutionPolicy Bypass -File C:\temp\myscript.ps1

# Copy script to target drive
cp "E:\vscode ai project\YT-rip\download_artists_v8.ps1" "D:\download_artists_v8.ps1"

# Copy fresh cookies
cp "C:\Users\jerme\Downloads\cookies.txt" "D:\cookies.txt"
```

## Changelog
- 2026-04-14: Created from Claude memory — source: conversation history
