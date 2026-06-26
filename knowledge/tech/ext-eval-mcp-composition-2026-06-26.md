---
title: "External Eval — MCP Server Composition (FastMCP) to Expand Our Data/Tool Surface"
status: SURFACED
created: 2026-06-26
---

# MCP Server Composition — Expanding Our Data/Tool Surface

**Goal:** Give Claude Code our meta tools *plus* Scryfall / 17Lands / EDHREC /
Moxfield / Spicerack / Commander Spellbook / MTGGoldfish tools (from j4th's
server) *plus* mtg-sim's simulation tools, ideally behind one composition layer,
following artillect's stateful/stateless split.

All claims below were fetched/read on 2026-06-26 (primary sources, not memory).
This doc is READ-ONLY research + a build spec — no code was changed.

---

## 0. Corrections to the prior audit (`thingstolookinto.md`, 2026-06-21)

Verified against live primary sources today. Three corrections:

1. **FastMCP 3.x EXISTS and is GA.** The 2026-06-21 audit said *"FastMCP 3.x is
   WRONG; there is no FastMCP 3.x (current is 2.x)."* That is now stale.
   - j4th's `pyproject.toml` pins `fastmcp>=3.2.0` (and installs cleanly via
     `uvx`, so 3.2.0 is a normal PyPI release, not a pre-release).
   - jlowin.dev published *"FastMCP 3.0 is GA"* and the live composition docs at
     gofastmcp.com mark `namespace=` mounting as *"new in version 3.0.0"*.
   - Note: a raw read of `pypi.org/pypi/fastmcp/json` reported `info.version =
     2.14.7` (Apr 13 2026). That is almost certainly a summarizer/`info.version`
     (latest-stable-at-snapshot) artifact — it is overridden by three
     independent primary sources (GA blog, live 3.0 docs, j4th's working
     `>=3.2.0` pin). **Treat FastMCP 3.x as current.** Before building, run
     `uv pip show fastmcp` / `python -c "import fastmcp,sys;print(fastmcp.__version__)"`
     to confirm the exact installed version and lock the API.
2. **KaminaDuck/scryfall-mcp is Apache-2.0, NOT no-license.** The audit filed it
   under "NO LICENSE -> reference only." Actual: Apache-2.0 (badge + README) =
   reuse-with-attribution OK. (We likely don't need it — j4th already covers
   Scryfall — but the license bar is lower than recorded.)
3. **artillect/mtg-mcp-servers: confirmed NO LICENSE file** = all-rights-reserved
   -> architecture/ideas only, clean reimplement, never copy code. (Audit was
   correct here.)

---

## 1. What we have today (read from disk)

`E:\vscode ai project\mtg-meta-analyzer\mcp_server\`

- **`server.py`** — `from mcp.server.fastmcp import FastMCP` -> i.e. **FastMCP
  1.0, the copy bundled inside the official `mcp` SDK**, NOT the standalone
  `fastmcp` package. `requirements.txt` pins `mcp>=1.27`; there is no `fastmcp`
  dependency. This is the single most important fact for the plan: **our server
  is on FastMCP 1.0, which does not have the 3.x `mount(namespace=...)` /
  proxy-composition surface.**
- **Tools (5, all read-only, `annotations=_READ_ONLY`):** `list_decks`,
  `get_matchup`, `get_field_position`, `search_matchups`, `search_strategy_docs`
  (Pinecone-backed; degrades gracefully). Entry: `mcp.run()` over stdio.
- **Design strengths already in place** (keep these — they are exactly what a
  good MCP is judged on): explicit `source` provenance on every win rate,
  structured `deck_not_found` with fuzzy suggestions, discovery-first
  (`list_decks`), pure/tested tool logic in `tools.py` (no MCP import) wrapping
  `analysis/win_rates.py`.
- **Registration:** `.mcp.json` -> one stdio server `mtg-meta`:
  `python -m mcp_server.server`.
- **Tests:** `tests/test_mcp_server.py` import the *pure* `tools.py`, so a
  FastMCP swap in `server.py` does not touch them.

`E:\vscode ai project\mtg-sim\` — standalone repo (CLAUDE.md: *"no cross-repo
Python dependencies"*). CLI drivers are the natural tool surface:
`sim.py` (goldfish), `bo3_gauntlet.py` (gauntlet), `run_matchup.py`,
`sb_optimizer.py`, `event_simulator.py`, `sim_bridge.py`, `meta_bridge.py`.
**No MCP server exists in mtg-sim yet.**

---

## 2. The external repos (fetched 2026-06-26)

### j4th/mtg-mcp-server — **MIT** — TOP TARGET
- `pyproject.toml`: `name="mtg-mcp-server"`, `requires-python=">=3.12"`,
  `dependencies = fastmcp>=3.2.0, httpx>=0.28, pydantic>=2, pydantic-settings>=2,
  cachetools>=6, tenacity>=9, structlog>=24, smithery>=0.4.4, selectolax>=0.4.7`.
  Console script: **`mtg-mcp-server = "mtg_mcp_server.server:main"`**.
- **69 tools, 19 prompts, 21 resource templates, 1340 tests / 88% cov.**
- Internally **already composed** as mounted sub-servers with namespaces:
  `scryfall_` (REST), `spellbook_` (Commander Spellbook), `draft_` (17Lands),
  `edhrec_` (scraped, feature-flagged), `bulk_` (Scryfall Oracle bulk),
  `moxfield_` (reverse-engineered, feature-flagged), `spicerack_` (tournament
  API), `goldfish_` (MTGGoldfish HTML scrape, feature-flagged), plus an
  un-namespaced `workflows` set that composes across services with partial-
  failure tolerance. Scraping/undocumented backends are **off by default behind
  pydantic-settings env flags** — enable explicitly.
- Install/run: `uvx mtg-mcp-server` or `uv tool install mtg-mcp-server`;
  `claude mcp add mtg -- uvx mtg-mcp-server`.
- **License action:** depend on / mount as-is; keep its LICENSE, attribute
  "j4th/mtg-mcp-server (MIT)". Because we run it as its own process (uvx), its
  deps never collide with ours.

### artillect/mtg-mcp-servers — **NO LICENSE -> reference only**
- Two separate processes (FastMCP + httpx): **`mtg_server.py` = STATEFUL** (deck
  upload, draw, hand contents, mulligan, sideboarding — holds game zones) and
  **`scryfall_server.py` = STATELESS** API proxy (search / random / lookup, no
  session state). Both wired into the client config as two independent stdio
  servers.
- **Use:** copy the *idea* (one stateful game-zone server + one stateless query
  server, mounted/registered side by side), reimplement from scratch. **Do not
  copy code.** This is the template for "sim = stateful, meta = stateless."

### KaminaDuck/scryfall-mcp — **Apache-2.0** (corrected) — optional
- TypeScript / Node 18+. Card search (Scryfall syntax), artwork URLs, hi-res
  image + art-crop download, and a local-image DB with integrity tools
  (`verify_database`, `scan_directory`, `clean_database`, `database_report`).
- **Use:** j4th already gives us Scryfall, so skip unless we specifically want a
  local card-image cache with integrity verification — then borrow the
  checksum/scan pattern (Apache-2.0, keep NOTICE + attribute).

### jlowin/fastmcp (FastMCP 3.x) — **Apache-2.0** — the engine
- Composition API (live docs):
  - `parent.mount(child)` = **live link** (child's tools/resources/prompts show
    through the parent; adding a tool to the child after mount is immediately
    visible). `parent.import_server(child)` = **static copy** at call time.
  - `parent.mount(child, namespace="meta")` (new in 3.0) prefixes tool names ->
    `meta_<tool>`. In 3.x, "mount" is internally just a *Provider* (sources
    components) + a *Transform* (adds the namespace prefix); you can chain
    transforms (rename / namespace / filter / version / secure).
  - **Remote/other-process mounting via proxy:** wrap an external server as a
    proxy and mount it. The docs show `mcp.mount(create_proxy(...),
    namespace="api")`; the config/stdio path is `FastMCP.as_proxy(<MCPConfig
    dict>)`. This lets us mount j4th (a *separate* process via `uvx`) without
    importing its package or merging dependency trees.

---

## 3. Plan

Three deliverables (a) upgrade our server to FastMCP 3.x, (b) add j4th's tools
next to ours, (c) split sim (stateful) + meta (stateless) as two sub-servers.

There are **two composition strategies**; pick per need:

- **Strategy A — Multi-server registration (RECOMMENDED baseline).** List each
  server independently in `.mcp.json`. Claude Code natively loads many MCP
  servers at once, so Claude sees `list_decks`, j4th's 69 tools, and sim tools
  side by side with **zero composition code**, each in its own isolated process.
  This is the lowest-risk way to "get Scryfall/17Lands/EDHREC tools next to our
  meta tools."
- **Strategy B — Single-endpoint orchestrator (FastMCP `mount`/proxy).** Build
  one parent FastMCP 3.x server that proxy-mounts all three under namespaces
  (`meta_*`, `sim_*`, `mtg_*`). Needed only when a downstream client must see
  **one** server (publishing, a non-Claude-Code client, or to apply cross-
  cutting transforms/auth/filtering). More code, more moving parts.

Recommendation: **ship A first** (it satisfies the whole brief for Claude Code),
then add B as a value-add once A is proven.

---

### Item (a) — Upgrade/confirm OUR server on FastMCP 3.x
**Value 4 · Effort S · Risk Low-Med**

Why: FastMCP 1.0 (bundled in `mcp`) lacks the 3.x composition surface; to mount
anything (Strategy B) or to align with j4th we move to the standalone `fastmcp`.
Even for Strategy A this is worth doing for the modern decorator/test client,
but A technically works on our current 1.0 server unchanged.

Steps:
1. `pip install "fastmcp>=3.2.0"`; confirm `python -c "import fastmcp;print(fastmcp.__version__)"`.
2. In `mcp_server/server.py` swap the import:
   `from mcp.server.fastmcp import FastMCP` -> `from fastmcp import FastMCP`.
   The `FastMCP("mtg-meta-analyzer")` constructor, `@mcp.tool(...)`, and
   `mcp.run()` are API-compatible. **Verify the `annotations=` kwarg** on
   `@mcp.tool` against the installed 3.x signature (our `_READ_ONLY` dict);
   if the kwarg moved, port to the 3.x tool-annotation form (functionally:
   readOnly/idempotent hints).
3. Add `fastmcp>=3.2.0` to `requirements.txt` (keep `mcp>=1.27`; `fastmcp`
   pulls a compatible `mcp` transitively).
4. Smoke test with the FastMCP in-memory test client (3.x ships one) instead of
   manual stdio. Existing `tests/test_mcp_server.py` still pass unchanged
   (they import pure `tools.py`).
5. `.mcp.json` entry is unchanged (`python -m mcp_server.server`).

Files (OURS): `mtg-meta-analyzer/mcp_server/server.py`,
`mtg-meta-analyzer/requirements.txt`. (Optional new test:
`tests/test_server_fastmcp.py` using the in-memory client.)

Risk: `annotations=` signature drift between SDK-FastMCP-1.0 and standalone-3.x;
Python floor 3.10 (we run 3.13 — fine; j4th wants 3.12+, also fine).

---

### Item (b) — Put j4th's Scryfall/17Lands/EDHREC tools next to ours
**Value 5 · Effort S (Strategy A) / M (Strategy B) · Risk Low**

**Strategy A (do this):**
1. Install isolated: `uvx mtg-mcp-server` (no venv pollution).
2. Register beside ours. Edit `mtg-meta-analyzer/.mcp.json`:
   ```json
   {
     "mcpServers": {
       "mtg-meta": { "type": "stdio", "command": "python",
                     "args": ["-m", "mcp_server.server"], "env": {} },
       "mtg":      { "type": "stdio", "command": "uvx",
                     "args": ["mtg-mcp-server"], "env": {} }
     }
   }
   ```
   Or one-shot: `claude mcp add mtg -- uvx mtg-mcp-server`.
3. Turn on only the backends we trust. j4th gates scraped/reverse-engineered
   backends (edhrec_, moxfield_, goldfish_) behind pydantic-settings env flags
   — leave them off initially; keep `scryfall_`, `draft_` (17Lands),
   `spellbook_`, `bulk_`, `spicerack_`. Set the flags in the server's `env` map
   once we read its settings names from its README/`config`.
4. Approve the new project-scoped server on first `claude` launch.

No double-prefixing, full process isolation, instant rollback (delete the entry).

**Strategy B (single endpoint, later):** proxy-mount j4th inside our
orchestrator (see Item c). Because j4th already namespaces internally
(`scryfall_*` etc.), mount it **without** an extra prefix (or a short one like
`mtg`) to avoid ugly `mtg_scryfall_search_cards` names.

Files (OURS): `mtg-meta-analyzer/.mcp.json` (+ orchestrator in Item c for B).
License: keep j4th's MIT LICENSE/attribution; we are consuming, not copying.

---

### Item (c) — Sim (stateful) + Meta (stateless) as two sub-servers (artillect pattern)
**Value 4 · Effort M (job-style sim) / L (true stateful session) · Risk Med**

Map artillect's split onto us: **meta-analyzer = the stateless query server (we
have it)**; **mtg-sim = a new stateful server**. Reimplement the *pattern* only
(artillect = no license).

**c1. New sim MCP server** — lives **inside mtg-sim** to respect its
"standalone, no cross-repo deps" rule. Mirror our meta layout:
`mtg-sim/mcp_server/tools.py` (pure logic wrapping the drivers) +
`mtg-sim/mcp_server/server.py` (`from fastmcp import FastMCP`; `@mcp.tool`).

Two flavors of "stateful":
  - **Job-style (recommended first, Effort M):** request/response tools that
    invoke the existing drivers and return parsed results — e.g.
    `goldfish_deck(deck, games)` -> wraps `sim.py`; `run_gauntlet(deck, games,
    field)` -> wraps `bo3_gauntlet.py`; `optimize_sideboard(...)` -> wraps
    `sb_optimizer.py`; `list_decks()` -> APL/deck registry. Each shells the CLI
    (or imports the driver fn) and parses FWR/kill-turn from output. This is the
    natural fit for mtg-sim's batch design and matches the ARL surface.
  - **True stateful session (artillect-faithful, Effort L):** session-keyed game
    state held in server memory — `start_game(deck) -> session_id`, then
    `draw`, `play`, `mulligan`, `sideboard`, `state(session_id)`. Higher value
    for interactive analysis but mtg-sim's engine is built for batch sim, not
    incremental external stepping; treat as a follow-up.

Mark sim tools `readOnlyHint=False` for session mutators; goldfish/gauntlet jobs
are effectively read-only (`readOnlyHint=True`, `openWorldHint=False`).

**c2. Compose.** With FastMCP 3.x, two routes again:
  - **Strategy A:** add a third `.mcp.json` entry `mtg-sim` ->
    `python -m mcp_server.server` (cwd = mtg-sim). Done.
  - **Strategy B — orchestrator** (new file, e.g.
    `mtg-meta-analyzer/mcp_server/compose.py`): a parent FastMCP that
    **proxy-mounts all three as separate stdio processes** (keeps mtg-sim's
    standalone rule intact — no Python import across repos):
    ```python
    from fastmcp import FastMCP
    parent = FastMCP("mtg-suite")
    meta = FastMCP.as_proxy({"mcpServers": {"meta": {"command": "python",
            "args": ["-m", "mcp_server.server"], "cwd": r"...\mtg-meta-analyzer"}}})
    sim  = FastMCP.as_proxy({"mcpServers": {"sim": {"command": "python",
            "args": ["-m", "mcp_server.server"], "cwd": r"...\mtg-sim"}}})
    mtg  = FastMCP.as_proxy({"mcpServers": {"mtg": {"command": "uvx",
            "args": ["mtg-mcp-server"]}}})
    parent.mount(meta, namespace="meta")   # -> meta_list_decks, ...
    parent.mount(sim,  namespace="sim")    # -> sim_run_gauntlet, ...
    parent.mount(mtg)                      # j4th already self-namespaced
    if __name__ == "__main__": parent.run()
    ```
    Then `.mcp.json` registers ONLY `mtg-suite` -> `python -m mcp_server.compose`.
    **Verify `as_proxy`/`mount` signatures against the installed 3.x** (the 3.0
    composition rewrite changed internals; the config-dict + `namespace=` shapes
    above match the live docs but pin them before relying on them).

Files (OURS): NEW `mtg-sim/mcp_server/server.py`, `mtg-sim/mcp_server/tools.py`,
`mtg-sim/requirements.txt` (+`fastmcp>=3.2.0`), `mtg-sim/.mcp.json` (A) **and/or**
NEW `mtg-meta-analyzer/mcp_server/compose.py` + edited
`mtg-meta-analyzer/.mcp.json` (B). Tests: `mtg-sim/tests/test_mcp_tools.py`
(pure-layer, mirror our meta tests).

Risk: parsing CLI stdout is brittle — prefer importing driver functions and
returning structured dicts; cold-start latency of three child processes under
the orchestrator; engine wasn't built for interactive stepping (defer c1's true-
session flavor).

---

## 4. Recommended sequence
1. **(b) Strategy A** — register `mtg` (uvx j4th) in `.mcp.json`. *Biggest win,
   smallest effort; unblocks Scryfall/17Lands/EDHREC immediately.*
2. **(a)** — migrate our server to `fastmcp>=3.2.0` (import swap + req + test).
3. **(c) c1 job-style + Strategy A** — new mtg-sim MCP server, third `.mcp.json`
   entry.
4. **(c2/b) Strategy B orchestrator** — only if/when a single endpoint is
   required; verify `as_proxy`/`mount` against installed FastMCP first.

## 5. License ledger (verified today)
| Repo | License | How we may use it |
|---|---|---|
| jlowin/fastmcp | Apache-2.0 | Depend on; keep NOTICE + attribute |
| j4th/mtg-mcp-server | MIT | Mount/consume as-is; keep LICENSE + attribute |
| KaminaDuck/scryfall-mcp | **Apache-2.0** (corrected) | Reuse-with-attrib OK; optional (img-cache integrity idea) |
| artillect/mtg-mcp-servers | **No license** | Pattern/ideas only; clean reimplement; never copy |

## 6. Open items to verify before building
- Exact installed `fastmcp` version + `as_proxy`/`mount(namespace=)` signatures.
- `@mcp.tool(annotations=...)` form in standalone 3.x vs our `_READ_ONLY` dict.
- j4th's pydantic-settings env-flag names for enabling/disabling backends.
- Whether to import mtg-sim driver fns vs shell out (prefer import -> structured).

## Changelog
- 2026-06-26: Created (SURFACED). Fetched j4th/artillect/KaminaDuck/fastmcp,
  read our `mcp_server/` + mtg-sim drivers. Corrected prior audit on FastMCP 3.x
  (GA, real) and KaminaDuck license (Apache-2.0, not no-license).
