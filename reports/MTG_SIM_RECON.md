# MTG_SIM_RECON.md

Reconnaissance report on `E:\vscode ai project\mtg-sim\` produced prior to polyrepo publication. This is a facts document — not a plan. No action has been taken; no files modified. HANDOFF-02 will be drafted separately once these findings are reviewed.

## Top-line summary

| Dimension | Value |
|---|---|
| Tracked files | 604 |
| Python LOC | ~44,900 |
| Git commits | 257 (all by Zuxas) |
| Branch | `master` (needs rename to `main`) |
| Remote | none |
| Secrets in history | **none** — only placeholder refs in `.env.template` and error messages |
| Personal names in source | **none** — all apparent hits are MTG card names (e.g., "Hanweir Garrison") |
| Hardcoded paths | **many** — concentrated in one cache file, see §3.1 |
| **Blocker issue** | `.gitignore` is corrupt (UTF-16 BOM), which let ~60 files leak into tracking |

**Posture:** This repo is closer to public-ready than I expected on the code side. The scrub is not about leaked credentials (there are none). It's about cleaning up the ~60 files that shouldn't have been tracked in the first place, one cache file with hardcoded paths, and a missing-dependencies-manifest problem that would break any fork's clone-and-run flow.

## 1. Directory structure

```
mtg-sim/
├── .claude/                  1 file
├── .git/                     (257 commits, master, no remote)
├── api/                      2 files
├── apl/                      87 files   <- archetype action priority lists
├── data/                     53 files   <- card data, decks, cache, logs
│   ├── auto_apls/            0
│   └── matchup_jobs/         59 files
├── decks/                    66 files   <- deck .txt lists
├── docs/                     18 files   <- MTG rules, oracle refs, audits
├── engine/                   31 files   <- game state, combat, mana
├── graphify-out/             (derived output)
│   └── cache/                125 files  <- should be ignored
├── logs/                     59 files   <- runtime logs, should be ignored
├── ml/                       18 files   <- training pipeline
├── output/                   3 files
├── reports/                  6 files
│   └── legacy_gauntlet/      7 files
└── tests/                    2 files    <- only __init__.py + test_api.py

46 loose .py files at repo root
```

46 files directly at the root is a lot of loose Python. Some are drivers (`sim.py`, `run_matchup.py`), some are one-offs (`compare_lists.py`, `consensus_75.py`), some are test scripts (`test_adeline.py`, `test_apls.py`, etc. — 11 `test_*.py` files at root, not in `tests/`). Worth noting for HANDOFF-02 but not a publication blocker.

## 2. Git state

- **Repo type:** active local git repo with real history
- **Commits:** 257, all authored as `Zuxas`
- **Branch:** `master` — will need `git branch -M main` before push
- **Remote:** none configured
- **Working tree dirty:** yes — many `__pycache__/*.pyc` show as modified/deleted, plus 4 APL files modified. None of the uncommitted changes are publication-relevant; they're runtime churn.
- **History secret scan:** ran the strict pattern (`sk-ant-*`, `sk-*`, `ghp_*`, `AKIA*`, PGP/SSH headers, `(ANTHROPIC|OPENAI|DISCORD|GITHUB|HUGGINGFACE|SLACK)_(API_KEY|TOKEN)`). Zero real matches. The only hits were:
  - `.env.template` line `ANTHROPIC_API_KEY=sk-ant-api03-PASTE_YOUR_KEY_HERE` (intentional placeholder, not a real key)
  - `apl/auto_apl.py` string `"Create .env with ANTHROPIC_API_KEY=sk-ant-..."` (help text)
  - `apl/auto_apl.py` parser `if line.startswith("ANTHROPIC_API_KEY="):` (env loader code)

  All three are code that *talks about* the env var, not content that *is* a secret. **History is clean.** No rewrite needed.

- **Commit messages:** unscanned for personal content. Spot-check of recent 5: all MTG-technical, no personal refs. Full-message scan should happen before push but is low-risk.

## 3. Scrub findings

### 3.1 Hardcoded local paths — **one cache file, many references**

`data/playbook_cache.json` is a tracked 20K+ line JSON cache with 20+ references to `E:\vscode ai project\My-Website\...`. Every entry has a `"source_file"` field pointing at a local HTML path. Example:

```json
"source_file": "E:\\vscode ai project\\My-Website\\amulet-titan-playbook.html"
```

This is generated/cached content, not hand-written. For a fork it's useless (points at paths they don't have) and it leaks your local layout.

**Options (for HANDOFF-02 to decide):**
1. Remove from tracking, add to `.gitignore`, regenerate on demand.
2. Rewrite all `source_file` values to relative paths before the first commit.
3. Delete entirely and let fork users rebuild the cache.

Option 1 is cleanest — this kind of cache shouldn't be in source control anyway.

Other hardcoded-path hits:
- `claude_run.py:3` — usage string `python E:\vscode ai project\mtg-sim\claude_run.py your_script.py`. Small, easy edit. Change to `python claude_run.py your_script.py`.

No other hardcoded paths in Python source or markdown.

### 3.2 Personal names — **zero real hits**

Grep for `jermey|zuxas|caleb|troubleshot|tien|garrison|urbae|foxy|rehgar` across `*.py`, `*.md`, `*.txt`:
- `data/comp_rules.txt:5805` — WotC rules text referencing MTG card "Hanweir **Garrison**". False positive.
- `docs/amulet_titan_oracle.txt:120` — Scryfall Oracle text for the same card. False positive.

No hits in Python source, no hits for `zuxas` or `jerme` in any text file.

### 3.3 Secrets and credentials — **zero real hits**

No `.env` files tracked (only `.env.template` with placeholder). No `*.cookies*`, `*.pem`, `*.key`, `secrets*`, or `credentials*` files found. Source references to `ANTHROPIC_API_KEY` are all legitimate env-var reads or help strings.

### 3.4 Cookie/session artifacts — **zero hits**

No cookies.txt, no browser session artifacts, no `__Secure-*PSID` or similar.

## 4. The .gitignore problem

This is the most important finding.

`.gitignore` is encoded as **UTF-16 LE with a byte-order mark** (hex dump: `ff fe 5f 00 5f 00 70 00 79 00 63 00 61 00 63 00 68 00 65 00 5f 00 5f 00 2f 00 0d 00 0a 00`). It contains a single rule: `__pycache__/`. But git expects UTF-8 or ASCII, so it reads the BOM as garbage characters and the rule never matched.

**Consequences in the current repo:**
- 54 `__pycache__/*.pyc` files are tracked
- 4 `*.err` and 5+ `*.log` files in `data/`, `ml/`, and `logs/` are tracked
- 125 files in `graphify-out/cache/` may be tracked (needs verification)
- `data/playbook_cache.json` is tracked (should probably also be ignored)

**Publication implications:**
- A fresh clone pulls all this junk down.
- Ongoing commits continue to churn on `.pyc` modifications unless the ignore file is fixed AND the existing entries are untracked.

**The fix is two steps:**
1. Rewrite `.gitignore` as proper UTF-8 with a real Python/project ignore set.
2. `git rm -r --cached` the already-tracked cache/log/err files.

Both land in HANDOFF-02 as prerequisite steps.

## 5. Dependencies — **undocumented**

No `requirements.txt`, `pyproject.toml`, `setup.py`, `Pipfile`, or `poetry.lock`. Imports scattered across ~45K LOC suggest at least:
- Standard library
- Likely: `requests` (Scryfall API calls inferred)
- Likely: `anthropic` SDK (`apl/auto_apl.py`, `output/claude_analysis.py`)
- Python 3.13 (confirmed — `Python 3.13.13`)

Any fork can't `pip install -r requirements.txt` because that file doesn't exist. Either HANDOFF-02 generates one (by grepping imports and mapping to PyPI packages) or the fork user does it themselves — but both mean running the code to find out what's missing. Not great for first impressions.

**Recommendation for HANDOFF-02:** run `pipreqs` or similar to auto-generate `requirements.txt` before first push.

## 6. README and documentation

- **`README.md`** (972 bytes) — a phased project pitch ("Phase 1 Data Layer (current)"). Outdated relative to the actual code (which is well past Phase 1–3). Generic and safe to ship but probably understates what's there. Good target for a rewrite that mirrors `claude-harness/README.md`'s structure.
- **`CLAUDE.md`** (1.2KB) — an Amulet Titan APL status note with sim WR, commit count, and current focus. Short, MTG-technical. No personal info. Would either need to stay as-is (meaningful to forkers interested in APL work) or be rewritten as a generic "Claude Code bootstrap" file matching the harness pattern.
- **`ARCHITECTURE.md`** (6KB), **`ROADMAP.md`** (12.6KB), **`MASTERPLAN.md`** (8KB), **`PHASE3_ARCHITECTURE.md`** (19KB), **`ORACLE_AUDIT.md`** (4.3KB) — substantial planning docs. Haven't been read; should be skimmed for personal content before ship. Likely safe given zero-hits on the personal-name scan, but worth a direct eyeball.
- **`docs/`** — 18 files, mostly MTG rules references (oracle text, rules audits). Reviewed filenames; no personal refs evident. Contents not deep-scanned.

## 7. Test coverage

- 11 `test_*.py` files at repo root (run style: `python test_adeline.py`, `python test_apls.py`, etc.)
- 1 test in `tests/` directory (`tests/test_api.py`)
- No pytest config, no CI config, no test runner declared.

Test quality and pass/fail state unknown — HANDOFF-02 should include a step that actually runs the tests and reports which pass before first push. Public repos that ship failing tests signal "abandoned," even when the code is good.

## 8. Size

- **Tracked files:** 604
- **Python LOC:** 44,889
- **Largest files (all APL archetypes):**
  - `apl/amulet_titan_grind_2026-04-18.py` — 142KB
  - `apl/amulet_titan_grind_2026-04-17.py` — 142KB (near-duplicate)
  - `apl/amulet_titan.py` — 142KB (canonical)
  - `apl/izzet_affinity.py` — 47KB
  - `apl/eldrazi_tron.py` — 40KB
  - `engine/game_state.py` — 39KB
- **Other large tracked files:**
  - `data/comp_rules.txt` — 965KB (WotC Comprehensive Rules, plain text)

### Dated APL snapshots

Three archetypes have date-stamped snapshot copies (from the tuning loop):
- `amulet_titan_grind_2026-04-17.py` and `_2026-04-18.py` in addition to the canonical `amulet_titan.py`
- `dimir_murktide_grind_2026-04-18.py` + `dimir_murktide.py`
- `boros_energy_grind_2026-04-18.py` + `boros_energy.py`

For a public release, the dated copies are likely noise — they represent intermediate tuning runs. Suggest keeping only the canonical versions. HANDOFF-02 decision point.

### `data/comp_rules.txt`

965KB of WotC's Comprehensive Rules in plain text. It's not sensitive, but it's a lot of bytes for something that's effectively a third-party reference document. Options for HANDOFF-02:
1. Keep tracked (adds ~1MB to clone size, but self-contained)
2. `.gitignore` and ship a `scripts/fetch_rules.py` that downloads it
3. Document the URL in README and leave fetching to the user

Option 2 is cleanest.

## 9. Critical issues (blockers for a clean first push)

In order of severity:

1. **Fix `.gitignore` encoding.** It's UTF-16 BOM and silently not working. Rewrite as UTF-8 with a proper ignore set (`__pycache__/`, `*.pyc`, `*.log`, `*.err`, `.env`, `data/playbook_cache.json`, `graphify-out/cache/`, `logs/`, `data/matchup_*.{log,err}`, `ml/pipeline_*.{log,err}`).
2. **Untrack existing cached/log files.** `git rm -r --cached` for the 54 `__pycache__` entries, the tracked `.log`/`.err` files, `data/playbook_cache.json`, and any others the rewritten `.gitignore` covers. Commit as "untrack generated artifacts."
3. **Fix hardcoded path in `claude_run.py:3`.** Trivial one-line edit.
4. **Generate `requirements.txt`.** Otherwise forks can't install.
5. **Rename `master` → `main` before push.**
6. **Decide on `data/playbook_cache.json`, `data/comp_rules.txt`, and the dated APL snapshots.** These are not security issues — they're size and cleanliness choices.

## 10. Open decisions for the user

Before HANDOFF-02 can be drafted cleanly, the following need answers:

1. **`data/playbook_cache.json`** — ignore it (regenerate on demand), rewrite paths, or delete?
2. **`data/comp_rules.txt`** (965KB) — ship, ignore with fetch script, or remove entirely?
3. **Dated APL snapshots** (`*_2026-04-17.py`, `*_2026-04-18.py`) — ship, or keep only canonicals?
4. **46 loose Python files at repo root** — ship as-is (messy but functional), or move test scripts into `tests/` and drivers into `scripts/` or `bin/`?
5. **README rewrite** — do a full pass (to match the `claude-harness` quality bar), or ship the current README and iterate?
6. **Tests** — run them first and only ship if they pass, or ship as-is?
7. **`CLAUDE.md`** — keep the Amulet Titan status note (it's genuine build-in-progress context for forkers), or replace with a generic bootstrap file?
8. **Commit strategy for cleanup** — one mega-commit "Prepare for public release," or a chain of small focused commits (fix .gitignore / untrack artifacts / fix path / add requirements.txt / etc.)?

Once those are decided, HANDOFF-02 writes itself.

## Files not modified by this recon

None. This was a read-only scan. The `mtg-sim/` directory is in the same state it was before I looked.
