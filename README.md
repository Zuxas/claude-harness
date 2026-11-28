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

## Prerequisites

- **Python 3.10+** (CI runs 3.12). The agents use `str.removeprefix` and modern
  type hints.
- **[Ollama](https://ollama.com)** running locally on `http://localhost:11434`
  for the local-model agents. The models the Python actually requests:
  | Model | Used for |
  |---|---|
  | `gemma4` (12B) | default for drift PRs, APL grinding/optimizing, analysis |
  | `gemma4:26b` | larger fallback in the APL code-gen preference chain |
  | `qwen2.5-coder:14b` | preferred code model for APL generation (falls back to `gemma4:26b` → `gemma4`) |

  Pull them with `ollama pull gemma4` etc. A missing model is skipped and the
  next in the chain is used (see `_APL_CODE_MODEL_PREFERENCE` in
  `agents/scripts/auto_pipeline.py`).
- **Sibling repos** `mtg-sim` and `mtg-meta-analyzer` checked out next to the
  harness (or pointed at via the env vars below) — the agents import `mtg-sim`'s
  `apl` / `data` / `engine` and read the analyzer's `mtg_meta.db`.
- **Python packages:** `pip install -r requirements.txt` (pytest; `anthropic` is
  an optional extra for the Claude code-gen path — see `requirements.txt`).

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

The PowerShell wrappers under `scripts/*.ps1` follow the same convention via
`scripts/_roots.ps1` (dot-sourced at the top of each wrapper). They honour the
same `HARNESS_ROOT` / `ZUXAS_PROJECT_ROOT` env overrides and otherwise derive the
roots from the wrapper's own location (`$PSScriptRoot`). Run
`powershell -File scripts\_roots.ps1 -ShowRoots` to print the resolved roots and
confirm they match your layout.

## Running the pipeline

The nightly work runs through two Python entry points (both take `--dry-run` to
print the plan without doing anything):

```bash
# Nightly orchestration (meta analysis + optional auto-pipeline).
python agents/scripts/nightly_harness.py --format modern --dry-run

# Archetype detection + APL generation on its own.
python agents/scripts/auto_pipeline.py --format modern --dry-run
# e.g. generate an APL for one deck (local Gemma, no Claude):
python agents/scripts/auto_pipeline.py --generate-apl "Boros Energy" --use-gemma
```

On Windows these are driven by the `scripts/*.ps1` wrappers and registered with
Task Scheduler (`scripts/register-harness-tasks.ps1`); see `CLAUDE.md` for the
scheduled-task layout and daily cadence.

## Tests

```bash
pip install -r requirements.txt
pytest -q
```

CI runs the same suite on every push and pull request
(`.github/workflows/tests.yml`).
