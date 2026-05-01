# Spec: GEXF Converter — JSON Snapshot to Gephi-Loadable Graph

**Status:** SHIPPED 2026-04-28 via execution-chain S7
**Created:** 2026-04-27 by claude.ai
**Target executor:** Claude Code
**Estimated effort:** 45-75 minutes
**Actual effort:** ~25 min
**Risk level:** Low (read-only on existing JSON; new output file format; harness-only)
**Dependencies:** D2 of `harness/specs/2026-04-28-project-visualization-mvp.md` (SHIPPED 2026-04-27); Gephi installed via D1.3 (SHIPPED 2026-04-27)

## Summary

Build `harness/scripts/json-to-gexf.py` -- a converter that reads a daily graph snapshot JSON (produced by `graph-snapshot.py`) and emits a GEXF 1.3 file that Gephi can open directly. Single-frame (current state) only; the animated time-lapse version is separate future work that requires 2+ weeks of accumulated snapshots.

This unlocks current-state Gephi rendering as a same-day capability instead of a 2-week-deferred one. Useful for: high-quality static current-state renders (Option 4 from the visualization conversation), one-off "what does the project look like right now" snapshots before major refactors, and the eventual time-lapse animation (the converter's GEXF schema is forward-compatible with adding `<spell>` timestamps later).

## Pre-flight reads (REQUIRED before starting)

1. `harness/CLAUDE.md` -- session start protocol
2. `harness/knowledge/tech/spec-authoring-lessons.md` v1.3 -- 10 lessons, especially:
   - `verify-identifiers-before-spec-execution` (verify gephi CLI args + xml libraries via canonical sources before pasting commands)
   - `prefer-version-over-help-for-preflight-probes` (use `python --version`, never `python --help`)
3. `harness/scripts/graph-snapshot.py` -- read the OUTPUT schema docstring at the top. The converter consumes that schema; any schema change in graph-snapshot.py would require updating this converter.
4. `harness/state/graph-snapshots/2026-04-28.json` -- example real input. Read the first ~200 lines to confirm the schema matches what the docstring claims.
5. GEXF 1.3 reference: https://gexf.net/schema.html -- bookmark, don't deep-read; use as reference during implementation. The format is XML with a documented schema; the converter only needs to emit a small subset.

## Background

`graph-snapshot.py` already produces clean structured JSON of the project graph (3076 nodes, 2516 edges as of first run). What's missing is the bridge to actual visualization tooling. Three paths considered:

- **Custom Python visualization (matplotlib/networkx).** Works but produces low-fidelity output. Already-tried territory in many academic graph projects; results look like undergraduate homework.
- **D3-force in browser.** High-fidelity but requires hosting a web page; overkill for a personal-use static render.
- **Gephi.** Industry-standard graph visualization with high-quality layout algorithms (ForceAtlas2, OpenOrd, Yifan Hu). Free. Already installed via D1.3. Native input format is GEXF.

The converter is a pure transform: read JSON, walk nodes + edges, emit GEXF 1.3 XML. No layout computation (Gephi handles that), no styling decisions baked in (those happen in Gephi UI), no network or external dependencies.

## Deliverables

### Deliverable 1: json-to-gexf.py

**Path:** `E:\vscode ai project\harness\scripts\json-to-gexf.py`

**Purpose:** Read a graph-snapshot JSON, emit equivalent GEXF 1.3 file.

**CLI:**
```
python json-to-gexf.py [--input PATH] [--output PATH] [--date YYYY-MM-DD] [--verbose]
```

**Defaults:**
- `--input`: today's snapshot at `harness/state/graph-snapshots/YYYY-MM-DD.json` (using local date)
- `--output`: `harness/visualizations/gephi/YYYY-MM-DD.gexf` (matching input date)
- `--date`: overrides today; lets you convert any historical snapshot. Mutually exclusive with `--input`.

**Output schema (GEXF 1.3):**

```xml
<?xml version="1.0" encoding="UTF-8"?>
<gexf xmlns="http://gexf.net/1.3" version="1.3">
  <meta lastmodifieddate="YYYY-MM-DD">
    <creator>json-to-gexf.py</creator>
    <description>Project graph snapshot from harness/state/graph-snapshots/YYYY-MM-DD.json</description>
  </meta>
  <graph mode="static" defaultedgetype="directed">
    <attributes class="node">
      <attribute id="0" title="type" type="string"/>
      <attribute id="1" title="top_folder" type="string"/>
      <attribute id="2" title="folder" type="string"/>
      <attribute id="3" title="size_bytes" type="integer"/>
      <attribute id="4" title="mtime_iso" type="string"/>
      <attribute id="5" title="in_degree" type="integer"/>
      <attribute id="6" title="out_degree" type="integer"/>
    </attributes>
    <attributes class="edge">
      <attribute id="0" title="type" type="string"/>
    </attributes>
    <nodes>
      <node id="<rel-path>" label="<basename>">
        <attvalues>
          <attvalue for="0" value="py"/>
          <attvalue for="1" value="mtg-sim"/>
          ...
        </attvalues>
      </node>
      ...
    </nodes>
    <edges>
      <edge id="0" source="<from-rel-path>" target="<to-rel-path>">
        <attvalues>
          <attvalue for="0" value="import"/>
        </attvalues>
      </edge>
      ...
    </edges>
  </graph>
</gexf>
```

**Implementation notes:**

1. **XML library:** use Python stdlib `xml.etree.ElementTree`. Do NOT add lxml or any other dep. ElementTree is sufficient for GEXF 1.3's complexity level.

2. **ID strategy:**
   - Node IDs: use the JSON's `id` field directly (relative path like `mtg-sim/engine/game_state.py`). Gephi accepts arbitrary string IDs; preserving paths makes debugging easier.
   - Edge IDs: sequential integers starting at 0. GEXF requires unique edge IDs but doesn't constrain format.
   - Node labels: use the file basename (e.g., `game_state.py` not `mtg-sim/engine/game_state.py`). Full path is in the `id` and as an attribute; label is what shows in Gephi's node display.

3. **Encoding:** write file as UTF-8. GEXF spec requires it. Set Python file mode `'w'` with `encoding='utf-8'` explicitly. Note: this is a generated XML file, not a .ps1 file -- the ASCII-only PowerShell rule does NOT apply here.

4. **Edge directionality:** the JSON's edges are directed (source = importer/wikilinker, target = imported/wikilinked). GEXF's `defaultedgetype="directed"` matches. Gephi can render undirected if user toggles in UI; the data preserves direction.

5. **Output directory:** create `harness/visualizations/gephi/` if it doesn't exist (alongside the existing `gource-*.mp4` files). Keep the visualizations/ subtree organized by tool: `gephi/` for GEXF outputs, gource MP4s at the top level (existing convention).

6. **Performance budget:** under 5 seconds for a 3000-node / 2500-edge snapshot. ElementTree's `tostring()` may slow down at much larger scales, but this is comfortably within range.

7. **Error handling:**
   - Input JSON not found: clear error message listing the path it tried, exit 2.
   - JSON parse error: surface the json.JSONDecodeError with line number, exit 3.
   - Schema mismatch (missing expected keys): print which key was missing, exit 4. Do NOT try to be clever about partial conversions.
   - Output directory creation fails: exit 5 with the OSError.
   - Otherwise exit 0 with one-line summary printed to stdout.

8. **Output line:**
   ```
   [json-to-gexf] 2026-04-28: 3076 nodes, 2516 edges -> harness/visualizations/gephi/2026-04-28.gexf (size: 487 KB)
   ```

### Deliverable 2: README in harness/visualizations/gephi/

**Path:** `harness/visualizations/gephi/README.md`

Brief reader-facing doc explaining:
- What's in this directory (GEXF files, one per date)
- How to open one in Gephi (File > Open > select .gexf)
- Recommended layout algorithms for this graph shape:
  - First pass: ForceAtlas2 with default settings. Good for getting a starting layout.
  - Refinement: Yifan Hu Multilevel for compact clusters, OR Fruchterman-Reingold for organic spread.
- Recommended visual settings:
  - Node size: by `out_degree` (highly-importing files become hubs)
  - Node color: by `top_folder` (one color per project: mtg-sim, harness, mtg-meta-analyzer, etc.)
  - Edge color: by `type` (wikilinks one color, imports another)
- How to regenerate: `python harness/scripts/json-to-gexf.py`

Keep it under 60 lines. This is operator docs, not a tutorial.

### Deliverable 3: Optional integration into session-snapshot.ps1

**Decision: skip for now.**

Could be tempting to call json-to-gexf.py in session-snapshot.ps1 alongside graph-snapshot.py. Don't. Reasons:
- GEXF files are derived data; the JSON is the source of truth. Running the converter on every session-snapshot adds runtime for no marginal value (you can regen GEXF anytime from any historical JSON).
- Disk usage grows linearly without benefit if every day generates a new GEXF that nobody opens.
- Use case is "I want a Gephi render right now," which is a manual on-demand action, not an automated one.

If a future session disagrees, that's a 5-minute addition (single block in session-snapshot.ps1's else branch, similar to the graph-snapshot block). Not now.

## Validation gates

**Gate 1: Script runs end-to-end on real input.**
- `python harness/scripts/json-to-gexf.py` exits 0
- Output file exists at expected path
- Output file is valid XML: `python -c "import xml.etree.ElementTree as ET; ET.parse(r'<output>')"` succeeds
- File size: between 100 KB and 10 MB for a 3000-node graph (sanity check; outside this range = something wrong)

**Gate 2: GEXF schema correctness.**
- Output validates against GEXF 1.3 conceptually:
  - Has `<gexf>` root with `version="1.3"` attribute
  - Has `<graph>` element with mode + defaultedgetype attributes
  - Node count matches JSON's `stats.total_nodes`
  - Edge count matches JSON's `stats.total_edges`
- Easy programmatic check:
  ```python
  import json, xml.etree.ElementTree as ET
  j = json.load(open('harness/state/graph-snapshots/2026-04-28.json'))
  ns = {'g': 'http://gexf.net/1.3'}
  t = ET.parse('harness/visualizations/gephi/2026-04-28.gexf')
  nodes = t.findall('.//g:node', ns)
  edges = t.findall('.//g:edge', ns)
  assert len(nodes) == j['stats']['total_nodes']
  assert len(edges) == j['stats']['total_edges']
  ```

**Gate 3: Gephi can open the file.**
- Manual gate: open the GEXF in Gephi. File loads without error dialog. Statistics panel shows the expected node/edge counts.
- Apply ForceAtlas2 layout for ~30 seconds; nodes should spread into a recognizable graph (not collapse to a point or explode off-screen).
- If Claude Code can't run Gephi GUI in its session, this gate is reported as "deferred to user" -- Jermey runs Gephi manually, confirms the load, reports back.

**Gate 4: Performance budget.**
- Conversion time: under 5 seconds for the current ~3000-node snapshot. Time it explicitly and report the number.

**Gate 5: Idempotency.**
- Run the converter twice on the same input. Outputs must be byte-identical (or differ only in `<meta lastmodifieddate>` if you choose to use real time). Determinism matters for diff-reviewing GEXF outputs across days.
- Recommended: hardcode `lastmodifieddate` to the input JSON's `snapshot_date` field, not `today()`. Ensures byte-identical re-runs for the same input.

## Stop conditions

**Stop and ship when:**
- Gates 1, 2, 4, 5 pass automatically + Gate 3 either passes (if Claude Code can verify) or is documented as deferred-to-user

**Stop and report (do NOT improvise) if:**
- ElementTree produces malformed XML (very unlikely; would indicate a Python install issue, not a code bug)
- Gate 5 (idempotency) fails -- means there's nondeterminism in the converter, fix before shipping
- Gephi rejects the file when Jermey opens it -- amend the spec, document the rejection reason in A1, fix, retest

**Do NOT do these things:**
- Do NOT add `<spell start=... end=...>` timestamps for time-lapse animation. That's separate future work; daily snapshots aren't accumulated yet.
- Do NOT compute layout positions in Python. Gephi does this; let it.
- Do NOT add styling/color attributes baked into the GEXF. Gephi UI handles styling per-session; baking it in reduces user flexibility.
- Do NOT add CLI flags for filtering (e.g., `--only-py`, `--exclude-folder`). YAGNI; user can prune in Gephi UI or pre-process the JSON if they want.
- Do NOT modify graph-snapshot.py or session-snapshot.ps1. Both shipped 2026-04-27; this converter is purely downstream.
- Do NOT add this to session-snapshot.ps1's automation. See Deliverable 3 rationale.

## Reporting expectations

After completion:
1. **Conversion stats:** input JSON path + size, output GEXF path + size, conversion time
2. **Gate results:** PASS/FAIL/DEFERRED per gate
3. **Sample output:** first 20 lines of the GEXF file (sanity check the structure looks right)
4. **Any deviations** from this spec (amendments, schema decisions that needed adjustment)

Then update spec status to SHIPPED, add line to RESOLVED.md, summary in chat.

## Mid-execution amendments

(Document any amendments here as work proceeds. Format: `### A1: <title>` then explanation.)

## Concrete steps (in order)

1. Pre-flight reads, especially graph-snapshot.py docstring + GEXF schema reference (10 min)
2. Stub the script: argparse setup, paths, basic JSON load (10 min)
3. Build the GEXF emit logic via ElementTree (20 min)
4. Run on real today's snapshot, eyeball first 20 lines of output (5 min)
5. Run Gates 1, 2, 4, 5 programmatically (10 min)
6. Write README.md in harness/visualizations/gephi/ (5 min)
7. (Optional) Notify Jermey to manually run Gate 3 in Gephi
8. Update spec status, RESOLVED.md, summary (5 min)

Total estimated wall time: 60 minutes including testing.

## Why this is bounded

Tempting scope creep:
- "While we're at it, add color/size attributes baked into the GEXF" -- Gephi handles this in UI per-session; baking reduces flexibility
- "Add a --filter flag to subset the graph" -- pre-process the JSON instead; converter stays a pure transform
- "Compute layout in Python and emit `<viz:position>` elements" -- that's Gephi's job; it does it better than networkx
- "Wire up time-lapse animation now" -- needs accumulated snapshots; comes later, separate spec

Resist all of these. The converter is a 100-line script that does one thing. The flexibility lives in Gephi's UI and in regenerating the GEXF whenever the source JSON changes.

## Future work this enables (NOT in scope)

- **Time-lapse animation** (target: 2026-05-12+, after 2+ weeks of daily JSONs). Extension of this converter that takes N daily snapshots and emits a single GEXF with `<spell start=... end=...>` per node/edge. Gephi's Timeline filter then animates the growth. Estimated 2-3 hours when ready, not the 4-6 originally estimated -- this converter does most of the per-snapshot work; the animation version just bolts on temporal merge logic.
- **Diff-GEXF**: take two daily snapshots, emit a GEXF showing only the deltas (nodes added/removed, edges added/removed). Useful for "what changed in the last week" snapshots. Estimated 30-45 min.
- **Per-folder GEXF subsets**: filter to single top_folder for focused renders. Estimated 15 min, but better as a CLI flag on this converter when the need is real.

## Changelog

- 2026-04-27: Spec created (PROPOSED). Drafted by claude.ai. Direct follow-on to D2 (graph-snapshot.py SHIPPED 2026-04-27) and D1.3 (Gephi installed SHIPPED 2026-04-27). Targeted for Claude Code execution whenever; no urgency.
- 2026-04-28: Status -> SHIPPED via execution-chain S7. ~25 min wall (well under 45-75 estimate; pure-transform was simpler than the spec budget anticipated).

  **Deliverables landed:**
  - `harness/scripts/json-to-gexf.py` (160 lines, pure stdlib, ElementTree + minidom)
  - `harness/visualizations/gephi/2026-04-28.gexf` (3098 nodes, 2522 edges, 2131 KB) — first real conversion
  - `harness/visualizations/gephi/README.md` (60 lines, operator-focused: how to open, recommended layouts, recommended visual settings, regenerate command)
  - Spec status PROPOSED -> SHIPPED (this changelog)

  **Validation gates:**
  - Gate 1 (end-to-end): PASS — script exits 0, output exists, valid XML, file size 2131 KB (within 100 KB - 10 MB sanity range)
  - Gate 2 (schema correctness): PASS — root version=1.3, graph mode=static defaultedgetype=directed, node count matches JSON (3098==3098), edge count matches (2522==2522)
  - Gate 3 (Gephi opens): DEFERRED to user — Claude Code can't run Gephi GUI from terminal; Jermey to manually verify when convenient
  - Gate 4 (performance): PASS — 0.62s conversion (well under 5s budget)
  - Gate 5 (idempotency): PASS — two consecutive runs with same input produce byte-identical output (md5: cc003fbab225 both runs); achieved by using snapshot_date for lastmodifieddate (not today()) per spec recommendation

  **Implementation notes that mattered:**
  - Pretty-printing via minidom adds ~30% file size vs unpretty but makes git-diff readable across days
  - JSON schema includes `top_folder` field which is in the spec's attribute table at id=1; converter handles correctly
  - ElementTree's namespace handling required `f"{{{GEXF_NS}}}elementname"` syntax throughout — verbose but correct

  **No new IMPERFECTIONS opened.** No new lessons compounded. Pure-transform spec; nothing surfaced that generalizes beyond "pure transforms are easier than they look."

  **Files touched (all unversioned harness):** `harness/scripts/json-to-gexf.py` (new), `harness/visualizations/gephi/README.md` (new), `harness/visualizations/gephi/2026-04-28.gexf` (new generated artifact), this spec.
