# Spec: Gource MP4 re-render with adjusted pacing (optional)

**Status:** PROPOSED (only execute if user wants different aesthetic)
**Created:** 2026-04-27 by claude.ai
**Target executor:** Claude Code
**Estimated effort:** 5-10 minutes (mostly Gource render time)
**Risk level:** Trivial (re-renders an existing artifact; no source code touched)
**Dependencies:** Original D1 Gource renders SHIPPED 2026-04-27. Gource + ffmpeg installed.

## Summary

The original Gource renders used `--seconds-per-day 1.5`, producing a 45.57s video for mtg-sim and 57.23s for mtg-meta-analyzer. If the user wants different pacing, this spec re-renders both with a user-specified value. **Only execute if the user has actively requested a re-render with a specified pacing value.**

## Pre-flight reads

1. `harness/specs/2026-04-28-d1-gource-renders.md` (SHIPPED) — original spec; do not re-execute the install or other parts, just adjust the render flag.

## Steps

1. **Confirm desired pacing value.** User must specify `--seconds-per-day N` value. If user said "longer" without a number, ask for the number; do not guess.
2. **Re-render mtg-sim** with the new value, overwriting `harness/visualizations/gource-mtg-sim.mp4`.
3. **Re-render mtg-meta-analyzer** with the new value, overwriting `harness/visualizations/gource-mtg-meta-analyzer.mp4`.
4. **Report new file sizes + video durations via ffprobe.**

## Reference Gource command (from D1 spec, only `--seconds-per-day` changes)

```powershell
cd "E:\vscode ai project\mtg-sim"
gource `
  --seconds-per-day <NEW_VALUE> `
  --auto-skip-seconds 1 `
  --max-files 0 `
  --hide mouse,progress `
  --bloom-multiplier 0.7 `
  --bloom-intensity 0.4 `
  --background-colour 0a0a0a `
  --font-size 16 `
  --output-framerate 30 `
  --output-ppm-stream - `
  | ffmpeg -y -r 30 -f image2pipe -vcodec ppm -i - `
    -vcodec libx264 -preset medium -pix_fmt yuv420p -crf 22 `
    -threads 0 -bf 0 `
    "E:\vscode ai project\harness\visualizations\gource-mtg-sim.mp4"
```

## Pacing reference

| seconds-per-day | mtg-sim duration (est) | meta-analyzer duration (est) |
|---|---|---|
| 0.5 | ~15s | ~19s |
| 1.0 | ~30s | ~38s |
| 1.5 (current) | 45.57s | 57.23s |
| 2.0 | ~60s | ~76s |
| 3.0 | ~90s | ~114s |
| 5.0 | ~150s | ~190s |

## Validation gates

**Gate 1:** Both MP4s exist at expected paths, sizes between 1 MB and 500 MB.
**Gate 2:** ffprobe duration is within ±20% of the table estimate above for the chosen pacing.

## Stop conditions

**Ship when:** Both gates pass.
**Stop and ask user if:** First render produces a file outside 1 MB - 500 MB or with duration wildly outside table estimate.

## Reporting expectations

1. New `--seconds-per-day` value used
2. New file sizes
3. New video durations from ffprobe
4. Confirmation that originals were overwritten (vs. saved separately)

## Changelog

- 2026-04-27 (post-D1): Spec created (PROPOSED) for optional re-render. Only execute on user request.
