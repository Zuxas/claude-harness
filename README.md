# claude-harness

Spec-first execution harness for the Zuxas workspace: drift detection, session
snapshots, nightly agents, and the lint/CI tooling that guards the sibling repos
(`mtg-sim`, `mtg-meta-analyzer`).

## Workspace layout

The harness expects to live alongside its sibling repos under one workspace:

```
<workspace>/
  harness/              # this repo
  mtg-sim/              # MTG simulator
  mtg-meta-analyzer/    # metagame analytics
  My-Website/           # public site (private)
```

On the maintainer's machine `<workspace>` is `E:\vscode ai project`. **You do not
have to reproduce that path.** Root resolution is derived from where the harness
actually sits (`agents/scripts/roots.py`), so a clone in any folder — a worktree,
CI, another machine — resolves correctly with no configuration.

## Configuring an alternate checkout

Paths are resolved by `agents/scripts/roots.py`. Each root is taken from an
environment variable if set, otherwise derived from the harness location:

| Variable | Overrides | Default (derived) |
|---|---|---|
| `ZUXAS_PROJECT_ROOT` | the workspace | parent of the harness repo |
| `HARNESS_ROOT` | this repo | the dir containing `roots.py`'s repo |
| `MTG_SIM_ROOT` | the simulator repo | `<workspace>/mtg-sim` |
| `MTG_META_ANALYZER_ROOT` | the analytics repo | `<workspace>/mtg-meta-analyzer` |
| `MTG_META_DB` | the meta DB | `<meta>/data/mtg_meta.db` |
| `MY_WEBSITE_ROOT` | the website repo | `<workspace>/My-Website` |
| `ZUXAS_BOOKS_DIR` | the books dir | `<workspace>/books` |

Set only what your layout needs; everything else derives automatically. For a
standalone harness clone with no siblings, point `MTG_SIM_ROOT` /
`MTG_META_ANALYZER_ROOT` at wherever those repos live (or leave them — scripts
that need a missing sibling will say so rather than silently targeting `E:\`).

> **Note:** the PowerShell wrappers under `scripts/*.ps1` still carry the old
> hardcoded workspace path; porting them to the same convention is tracked
> separately (see the open issues).

## Tests

```bash
pip install pytest
pytest -q
```

CI runs the same suite on every push and pull request
(`.github/workflows/tests.yml`).
