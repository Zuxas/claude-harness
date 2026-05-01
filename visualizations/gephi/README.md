# Gephi visualizations

GEXF 1.3 graph snapshots of the project, one per date. Generated from
`harness/state/graph-snapshots/<date>.json` by `harness/scripts/json-to-gexf.py`.

## Open in Gephi

1. File -> Open -> select a `<date>.gexf` from this directory
2. In the import dialog: Graph Type "Directed", "Append to existing workspace" off

## Recommended layout algorithms

- **First pass:** ForceAtlas2 with default settings. Run for 30-60s, watch the
  graph spread. Good starting layout for exploring overall structure.
- **For tight clusters:** Yifan Hu Multilevel. Compact, well-separated communities.
- **For organic spread:** Fruchterman-Reingold. Smoother edge distribution.

## Recommended visual settings

- **Node size:** by `out_degree` attribute (highly-importing files become hubs).
  Range 5-50 px works well for ~3000-node graphs.
- **Node color:** partition by `top_folder` (one color per project: `mtg-sim`,
  `harness`, `mtg-meta-analyzer`, `claude-skills`, etc.). Use the partition
  panel; assign distinct colors per category.
- **Edge color:** partition by `type` (wikilink vs import). Default 0.1 alpha
  to avoid overwhelming the node display.
- **Labels:** show only for top-N by degree (Filters -> Topology -> Degree Range,
  set min to ~10). Avoids label clutter on the long tail.

## Regenerate

Single date:
```
python harness/scripts/json-to-gexf.py
```

Specific date:
```
python harness/scripts/json-to-gexf.py --date 2026-04-28
```

Custom paths:
```
python harness/scripts/json-to-gexf.py --input <path.json> --output <path.gexf>
```

## Notes

- Files are byte-identical across re-runs from the same source JSON
  (idempotency gate per spec). Diff-friendly across days.
- Gephi's UI handles all layout + styling per-session; nothing is baked into
  the GEXF beyond raw structure + attributes.
- Time-lapse animation (multi-day animated growth) is separate future work
  per the spec; needs 2+ weeks of accumulated daily snapshots first.

Spec: `harness/specs/2026-04-28-gexf-converter.md`
