# Spec: Time-lapse animation prep

**Status:** PROPOSED (data not yet sufficient; spec is forward-looking infrastructure)
<!-- spec-ref-ok: json-to-gexf-timelapse.py is intentionally not yet built; this spec describes its future creation -->
**Created:** 2026-04-27 by claude.ai
**Target executor:** Claude Code
**Estimated effort:** 60-90 minutes
**Risk level:** LOW (additive scripting; consumes existing JSON; no engine code touched)
**Dependencies:**
- `harness/scripts/graph-snapshot.py` SHIPPED 2026-04-27 (D2 of project-visualization-mvp)
- `harness/specs/2026-04-28-gexf-converter.md` (PROPOSED) — sibling; ships single-frame GEXF, this spec extends to multi-frame
- Gephi installed (D1.3 SHIPPED 2026-04-27)
**Blocks:** Nothing. Output is infrastructure ready for use once 2+ weeks of daily JSONs accumulate.

## Summary

Build the multi-frame time-lapse pipeline that produces a Gephi-loadable GEXF with `<spell start=... end=...>` timestamps per node/edge. Consumes N daily JSON snapshots from `harness/state/graph-snapshots/`, emits a single GEXF that Gephi's Timeline filter can animate.

This spec is forward-looking: it builds the pipeline now while the design is fresh, but the actual rendered animation is meaningful only after 2+ weeks of daily JSONs accumulate (target: 2026-05-12 or later). The spec ships a working pipeline with N=1 (today's snapshot only) as a sanity check; future invocations against accumulated data produce real animations without further code changes.

## Pre-flight reads (REQUIRED)

1. `harness/scripts/graph-snapshot.py` — JSON schema this spec consumes
2. `harness/specs/2026-04-28-gexf-converter.md` — sibling spec; if SHIPPED, this spec extends it; if not SHIPPED, this spec includes a single-frame mode as a strict superset
3. `harness/state/graph-snapshots/2026-04-28.json` — example real input
4. GEXF 1.3 dynamics reference: https://gexf.net/dynamics.html — bookmark, read the `<spell>` and `<spells>` elements
5. `harness/CLAUDE.md` Rule 1, Rule 4

## Background

Static GEXF (sibling spec) renders one snapshot. Time-lapse needs dynamic GEXF: each node and edge has `<spell start=... end=...>` indicating when it existed. Gephi's Timeline filter animates by sliding a window across the time range.

The merge logic:
- For each node, find the FIRST date it appeared in any snapshot → `start`
- For each node, find the LAST date it appeared → `end` (or "open-ended" if it appeared in the most recent snapshot)
- Same for edges
- Node attributes (size_bytes, in_degree, etc.) can also be dynamic via `<attvalue start=... end=... value=...>` if they change across snapshots

## Deliverables

### D1: json-to-gexf-timelapse.py

**Path:** `E:\vscode ai project\harness\scripts\json-to-gexf-timelapse.py`

**CLI:**
```
python json-to-gexf-timelapse.py [--snapshots-dir PATH] [--output PATH] [--start-date YYYY-MM-DD] [--end-date YYYY-MM-DD] [--verbose]
```

**Defaults:**
- `--snapshots-dir`: `harness/state/graph-snapshots/`
- `--output`: `harness/visualizations/gephi/timelapse-YYYY-MM-DD-to-YYYY-MM-DD.gexf` (using actual date range)
- `--start-date`/`--end-date`: defaults to "all snapshots in dir"

**Behavior:**

1. Walk `--snapshots-dir`, load all JSON files matching `YYYY-MM-DD.json` within date range
2. Sort by date ascending
3. Build node lifespans: for each node ID, record `first_seen` and `last_seen` dates
4. Build edge lifespans: same logic
5. Emit GEXF 1.3 dynamic mode:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<gexf xmlns="http://gexf.net/1.3" version="1.3" mode="dynamic" timeformat="date">
  <meta lastmodifieddate="YYYY-MM-DD">
    <creator>json-to-gexf-timelapse.py</creator>
    <description>Time-lapse from N snapshots between START_DATE and END_DATE</description>
  </meta>
  <graph mode="dynamic" defaultedgetype="directed" timeformat="date" 
         start="<start-date>" end="<end-date>">
    <attributes class="node" mode="static">
      <!-- same as static GEXF -->
    </attributes>
    <nodes>
      <node id="<rel-path>" label="<basename>" 
            start="<first-seen>" end="<last-seen>">
        <attvalues>...</attvalues>
      </node>
      ...
    </nodes>
    <edges>
      <edge id="<idx>" source="..." target="..." 
            start="<first-seen>" end="<last-seen>">
        <attvalues>...</attvalues>
      </edge>
      ...
    </edges>
  </graph>
</gexf>
```

**N=1 special case:** if only one snapshot is in the date range, emit a static GEXF with `mode="static"` and no spell timestamps. Behaves identically to the sibling json-to-gexf.py converter for a single-snapshot input. This makes the spec self-validating: running the timelapse converter against today's single snapshot produces the same output as the static converter.

**Performance budget:** under 30s for 30 daily snapshots (a month of data).

**Implementation notes:**
- Use `xml.etree.ElementTree` (stdlib) — same as sibling spec
- Date format: ISO 8601 `YYYY-MM-DD` everywhere; matches GEXF `timeformat="date"`
- Edge IDs: sequential integers based on union of all snapshots (re-key on union, not per-snapshot)
- Node IDs: preserve from JSON (relative path)
- For nodes appearing in non-contiguous snapshots (gap days), default behavior: span the gap (treat as continuous existence). Document this assumption; alternative is to emit multiple `<spell>` elements per node, but that's complexity for a probably-rare case.

### D2: README addition

Update `harness/visualizations/gephi/README.md` (created by sibling spec) with a section on the time-lapse converter:
- When to use vs static converter
- How Gephi's Timeline filter consumes dynamic GEXF
- Recommended Timeline settings (window size, animation speed)
- Note that animation quality scales with snapshot count; needs 14+ snapshots for visually meaningful playback

### D3: Idempotency / determinism

Same as static converter:
- Output deterministic for same input set
- Re-running on same snapshot set produces byte-identical output (or differs only in lastmodifieddate)
- Recommendation: hardcode `lastmodifieddate` to the LAST snapshot date in the input set, not `today()`

## Validation gates

**Gate 1: N=1 mode works.**
Run with today's single snapshot only. Output should be static GEXF identical (or near-identical, allowing for `mode=` attribute) to what the sibling json-to-gexf.py produces. Validates that the multi-frame logic doesn't break the single-frame case.

**Gate 2: N=1 GEXF loads in Gephi.**
Same as sibling spec's Gate 3. Manual or deferred to user.

**Gate 3: Schema validity for multi-frame.**
For testing, manually create 3 small synthetic JSON snapshots (e.g., snapshot-day-1 has 3 nodes, snapshot-day-2 adds 1 node, snapshot-day-3 removes 1). Run the converter. Verify:
- All nodes that appear in any snapshot are in the GEXF
- Each node's `start` is the date of its first snapshot appearance
- Each node's `end` is the date of its last snapshot appearance (or absent / open-ended for nodes still present in last snapshot)

**Gate 4: Performance.**
Run-time under 30s with 30 synthetic snapshots. Time it explicitly.

**Gate 5: Idempotency.**
Run twice on same input, output byte-identical (modulo lastmodifieddate if it varies; recommendation: hardcode it).

**Gate 6: Real-world dry run.**
Run with whatever real snapshots exist (1 today, more accumulating daily). Output validates as XML, loads in Gephi without errors. Animation is sparse (only 1 day of data) but the pipeline works.

## Stop conditions

**Ship when:** Gates 1, 3, 4, 5, 6 pass. Gate 2 deferred to user.

**Stop and amend if:**
- Synthetic Gate 3 reveals incorrect lifespan logic (nodes flagged with wrong start/end)
- Performance gate fails (over 30s for 30 snapshots) — investigate, possibly switch from ElementTree to lxml or stream-write XML
- Gephi rejects the dynamic GEXF — possibly malformed `<spell>` elements; consult GEXF reference and amend

**DO NOT:**
- Do NOT add styling/layout decisions to the GEXF. Gephi UI handles those.
- Do NOT add `<spells>` (multiple spells per node) for gap-day cases in v1. Use single span. Add as future-work if gaps become common.
- Do NOT compute layout positions. Gephi does this.
- Do NOT add CLI flags for filtering nodes by type/folder. YAGNI; pre-process the JSON if filtering needed.
- Do NOT auto-render an MP4 from the dynamic GEXF. That requires Gephi's video export, which is UI-driven; can't easily script. User does this manually when ready.
- Do NOT attempt to rebuild the converter to load each snapshot lazily for memory efficiency. With reasonable snapshot count (< 100), full-load is fine.

## Reporting expectations

1. Sample output: 30 lines of generated GEXF showing `<spell>` elements
2. Synthetic Gate 3 results — start/end per node verified
3. Real-world Gate 6 results — file size, runtime, loads-in-Gephi confirmation deferred to user
4. Idempotency confirmation
5. Recommended next-action: when (date) does the user have enough snapshots for a visually meaningful animation?

Then update spec status to SHIPPED, summary in chat.

## Concrete steps (in order)

1. Pre-flight reads, especially GEXF dynamics docs (15 min)
2. Stub the script: argparse, snapshot enumeration, sort by date (10 min)
3. Build the lifespan-merge logic (20-25 min) — this is the core
4. Build GEXF emit (15 min)
5. N=1 special case + tests (5-10 min)
6. Synthetic 3-snapshot test for Gate 3 (10 min)
7. README addition for D2 (5 min)
8. Performance + idempotency gates (5 min)
9. Real-world dry run (5 min)
10. Commit + spec status (5 min)

Total: 90 min realistic, may exceed if Gephi dynamic format reveals quirks.

## Why this order

- Lifespan-merge logic before GEXF emit because if the merge is wrong, the GEXF is just wrapping wrong data
- N=1 special case before synthetic multi-frame test because N=1 is a strict subset; if it works, the harder case is more likely to work too
- Real-world dry run last because by then the synthetic tests have proven correctness; real-world is just file-size sanity check

## Future work this enables (NOT in scope)

- **Visually meaningful animation render** (target: 2026-05-12+, after 2+ weeks of accumulated snapshots). User opens the dynamic GEXF in Gephi, configures Timeline filter, exports MP4. Manual UI work; no further code needed.
- **Per-spell attribute changes** for animations that show a node "growing" (e.g., size_bytes change over time as a file grows). v1 keeps attributes static. Estimated 30-45 min addition when needed.
- **Diff-mode rendering** — show only nodes/edges that changed between two date ranges. Useful for "what changed last week" visualizations. Estimated 30 min.
- **Auto-render via headless Gephi.** Gephi has a CLI mode (`gephi-toolkit`) that could be scripted. Investigated separately; current state is "manual UI export."

## Why this is bounded

Tempting scope creep:
- "While we're at it, also auto-render the MP4" — Gephi UI export is the right path; CLI auto-render is a separate spec
- "Add a web preview using d3-force" — separate visualization stack, separate spec
- "Build a Python animation in matplotlib that doesn't need Gephi" — already considered and rejected (low fidelity)

Resist all of these. The converter is one transform: dated JSONs → dynamic GEXF. Everything else is downstream.

## Changelog

- 2026-04-27 (post-Stage-C-revert): Spec created (PROPOSED). Forward-looking infrastructure: ships now while design is fresh, produces meaningful output once 2+ weeks of daily JSONs accumulate. Targeted for Claude Code execution any time.
