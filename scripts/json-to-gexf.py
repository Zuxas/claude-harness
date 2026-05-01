#!/usr/bin/env python3
"""json-to-gexf.py -- Convert graph-snapshot JSON to GEXF 1.3 for Gephi.

Reads a daily project graph snapshot (produced by graph-snapshot.py) and
emits an equivalent GEXF 1.3 XML file that Gephi can open directly. Single-
frame (current state) only; time-lapse animation is separate future work.

Usage:
    python json-to-gexf.py [--input PATH] [--output PATH] [--date YYYY-MM-DD] [--verbose]

Defaults:
    --input   harness/state/graph-snapshots/<today>.json
    --output  harness/visualizations/gephi/<today>.gexf
    --date    overrides today; lets you convert any historical snapshot

Spec: harness/specs/2026-04-28-gexf-converter.md
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from xml.dom import minidom

SCRIPT_DIR = Path(__file__).parent.resolve()
HARNESS_ROOT = SCRIPT_DIR.parent
SNAPSHOTS_DIR = HARNESS_ROOT / "state" / "graph-snapshots"
GEPHI_OUT_DIR = HARNESS_ROOT / "visualizations" / "gephi"

GEXF_NS = "http://gexf.net/1.3"


def build_gexf(snapshot, snapshot_date):
    """Build GEXF 1.3 ElementTree from a graph-snapshot dict.

    Idempotent: same input -> byte-identical output (uses snapshot_date
    not today() for lastmodifieddate per spec gate 5).
    """
    ET.register_namespace("", GEXF_NS)
    gexf = ET.Element(f"{{{GEXF_NS}}}gexf", attrib={"version": "1.3"})

    meta = ET.SubElement(gexf, f"{{{GEXF_NS}}}meta",
                         attrib={"lastmodifieddate": snapshot_date})
    creator = ET.SubElement(meta, f"{{{GEXF_NS}}}creator")
    creator.text = "json-to-gexf.py"
    desc = ET.SubElement(meta, f"{{{GEXF_NS}}}description")
    desc.text = (f"Project graph snapshot from "
                 f"harness/state/graph-snapshots/{snapshot_date}.json")

    graph = ET.SubElement(gexf, f"{{{GEXF_NS}}}graph",
                          attrib={"mode": "static", "defaultedgetype": "directed"})

    # Node attributes schema
    node_attrs_decl = ET.SubElement(graph, f"{{{GEXF_NS}}}attributes",
                                    attrib={"class": "node"})
    node_attr_specs = [
        ("0", "type", "string"),
        ("1", "top_folder", "string"),
        ("2", "folder", "string"),
        ("3", "size_bytes", "integer"),
        ("4", "mtime_iso", "string"),
        ("5", "in_degree", "integer"),
        ("6", "out_degree", "integer"),
    ]
    for aid, title, atype in node_attr_specs:
        ET.SubElement(node_attrs_decl, f"{{{GEXF_NS}}}attribute",
                      attrib={"id": aid, "title": title, "type": atype})

    # Edge attributes schema
    edge_attrs_decl = ET.SubElement(graph, f"{{{GEXF_NS}}}attributes",
                                    attrib={"class": "edge"})
    ET.SubElement(edge_attrs_decl, f"{{{GEXF_NS}}}attribute",
                  attrib={"id": "0", "title": "type", "type": "string"})

    # Nodes
    nodes_el = ET.SubElement(graph, f"{{{GEXF_NS}}}nodes")
    for n in snapshot["nodes"]:
        node_id = n["id"]
        # Label = file basename for Gephi node display readability
        label = node_id.rsplit("/", 1)[-1] if "/" in node_id else node_id
        node = ET.SubElement(nodes_el, f"{{{GEXF_NS}}}node",
                             attrib={"id": node_id, "label": label})
        attvals = ET.SubElement(node, f"{{{GEXF_NS}}}attvalues")
        # Map: attr_id -> value (with stringify)
        attr_values = [
            ("0", str(n.get("type", ""))),
            ("1", str(n.get("top_folder", ""))),
            ("2", str(n.get("folder", ""))),
            ("3", str(n.get("size_bytes", 0))),
            ("4", str(n.get("mtime_iso", ""))),
            ("5", str(n.get("in_degree", 0))),
            ("6", str(n.get("out_degree", 0))),
        ]
        for aid, val in attr_values:
            ET.SubElement(attvals, f"{{{GEXF_NS}}}attvalue",
                          attrib={"for": aid, "value": val})

    # Edges
    edges_el = ET.SubElement(graph, f"{{{GEXF_NS}}}edges")
    for i, e in enumerate(snapshot["edges"]):
        edge = ET.SubElement(edges_el, f"{{{GEXF_NS}}}edge",
                             attrib={
                                 "id": str(i),
                                 "source": e["from"],
                                 "target": e["to"],
                             })
        attvals = ET.SubElement(edge, f"{{{GEXF_NS}}}attvalues")
        ET.SubElement(attvals, f"{{{GEXF_NS}}}attvalue",
                      attrib={"for": "0", "value": str(e.get("type", ""))})

    return gexf


def write_gexf(root_element, output_path):
    """Write GEXF tree to disk as UTF-8. Pretty-print via minidom for diff
    readability + idempotency."""
    rough_string = ET.tostring(root_element, encoding="utf-8")
    reparsed = minidom.parseString(rough_string)
    pretty = reparsed.toprettyxml(indent="  ", encoding="utf-8")
    with open(output_path, "wb") as f:
        f.write(pretty)


def main():
    parser = argparse.ArgumentParser(description="Convert graph-snapshot JSON to GEXF 1.3")
    parser.add_argument("--input", default=None,
                        help="Input JSON path (default: today's snapshot)")
    parser.add_argument("--output", default=None,
                        help="Output GEXF path (default: harness/visualizations/gephi/<date>.gexf)")
    parser.add_argument("--date", default=None,
                        help="Override snapshot date (YYYY-MM-DD); mutually exclusive with --input")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()

    if args.date and args.input:
        print("[json-to-gexf] ERROR: --date and --input are mutually exclusive", file=sys.stderr)
        sys.exit(1)

    if args.input:
        input_path = Path(args.input)
    else:
        date_str = args.date or datetime.now().strftime("%Y-%m-%d")
        input_path = SNAPSHOTS_DIR / f"{date_str}.json"

    if not input_path.exists():
        print(f"[json-to-gexf] ERROR: input JSON not found: {input_path}", file=sys.stderr)
        sys.exit(2)

    try:
        snapshot = json.loads(input_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[json-to-gexf] ERROR: JSON parse error in {input_path}: {e}", file=sys.stderr)
        sys.exit(3)

    # Schema validation
    required_keys = {"snapshot_date", "stats", "nodes", "edges"}
    missing = required_keys - set(snapshot.keys())
    if missing:
        print(f"[json-to-gexf] ERROR: input missing required keys: {sorted(missing)}",
              file=sys.stderr)
        sys.exit(4)

    snapshot_date = snapshot["snapshot_date"]

    if args.output:
        output_path = Path(args.output)
    else:
        output_path = GEPHI_OUT_DIR / f"{snapshot_date}.gexf"

    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        print(f"[json-to-gexf] ERROR: cannot create output dir: {e}", file=sys.stderr)
        sys.exit(5)

    t0 = time.time()
    gexf_root = build_gexf(snapshot, snapshot_date)
    write_gexf(gexf_root, output_path)
    elapsed = time.time() - t0

    n_nodes = len(snapshot["nodes"])
    n_edges = len(snapshot["edges"])
    size_kb = output_path.stat().st_size // 1024
    print(f"[json-to-gexf] {snapshot_date}: {n_nodes} nodes, {n_edges} edges "
          f"-> {output_path.relative_to(HARNESS_ROOT.parent) if output_path.is_relative_to(HARNESS_ROOT.parent) else output_path} "
          f"(size: {size_kb} KB, {elapsed:.2f}s)")
    sys.exit(0)


if __name__ == "__main__":
    main()
