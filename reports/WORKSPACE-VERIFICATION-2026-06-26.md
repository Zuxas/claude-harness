# Workspace Verification — 2026-06-26

Full-workspace status + backlog verification requested before any scrub/move/cleanup work.
Read everything; no shortcuts. This is the "where are we right now" baseline.

---

## 0. Headline findings

1. **All prior handoffs are accounted for. Only HANDOFF-04 (Pocock) is unexecuted** — it is the active one.
2. **HANDOFF-04's own premises are partly STALE** (verified false against disk):
   - Section 2 claims the ARL loop + `arl_steer.py`/`arl_status.py`/`loop_state.json` "exist in mtg-sim." **They do not.** ARL is spec-only — the spec was added to `mtg-sim/CLAUDE.md` on 2026-06-25 and is still uncommitted. No `loop_state.json`, no arl_*.py scripts.
     - => **Task 3.3 (add `hitl` field to `loop_state.json`) is NOT executable as written** — no file to edit, and the loop it gates isn't built.
   - Section 3.2 rationale ("ARL loop has no git safety net — HIGHEST PRIORITY") is **stale**: pre-push hooks DO exist on mtg-sim + mtg-meta-analyzer. They are PII/secret/path scrubbers, NOT Pocock destructive-command blockers (`push`/`reset --hard`/`clean`/`rebase`). So 3.2 is still genuinely undone, but the framing is wrong.
   - Task 3.1's skill list was from the workshop and is slightly stale vs the live repo: `diagnose` is now `diagnosing-bugs`; everything else still exists. The router is `ask-matt`.
3. **~6-week human-work gap.** harness/MEMORY.md session log + pending list stop ~2026-05-15. Daily automation (snapshot/drift/drift-PR) has run correctly every day through 2026-06-25, but no human-driven session touched the harness for ~42 days. mtg-sim + mtg-meta-analyzer last had real commits 2026-06-21 (docs/badges).
4. **The original HANDOFF-04 was reused.** HANDOFF-03-POSTMORTEM + SESSION-POSTMORTEM-2026-04-20 both queued "HANDOFF-04 = harness-personal private push." That number was reused for the Pocock workflow integration. The private-harness push has no execution doc and appears never done. (Decision needed: still wanted, or dropped?)

---

## 1. Handoff completion status

| Handoff | Topic | Status | Evidence |
|---|---|---|---|
| SESSION-POSTMORTEM-2026-04-20 | claude-harness + sim↔analyzer integration (HANDOFF-01 era) | ✅ DONE | 47 commits across 4 repos; postmortem on disk |
| HANDOFF-02 | Publish mtg-sim public | ✅ DONE | HANDOFF-02-POSTMORTEM (11 commits, repo live) |
| HANDOFF-03 | Update mtg-meta-analyzer public | ✅ DONE | HANDOFF-03-POSTMORTEM (11 commits) |
| (original) HANDOFF-04 | harness-personal PRIVATE push | ❓ NEVER DONE | queued in HANDOFF-03-POSTMORTEM + SESSION-POSTMORTEM-2026-04-20; no doc; number reused |
| HANDOFF-04 (current) | Pocock workflow integration | ⏳ ACTIVE / unexecuted | "awaiting review and activation"; this session begins it |
| mtg-sim/HANDOFF_2026-05-09 | RC DC Standard deck lock | ⏳ HISTORICAL/OPEN | RC DC was 2026-05-11/12 (past). 8 handler audits + Untapped scrape decision left open. Untracked in mtg-sim. |

---

## 2. Per-project status

### mtg-sim — ACTIVE, stable core
- Last commit `8f8064b` 2026-06-21 (docs: verified status badges). main, up to date with origin.
- Uncommitted: 3 modified (`CLAUDE.md` +328 lines ARL spec, `.gitignore`, `.claude/settings.local.json`), ~36 untracked (RC-prep data dumps, 9 test scripts, `AGENTS.md`, `.codex/`, `HANDOFF_2026-05-09.md`).
- Pre-push hook: EXISTS (secret/PII/path scrubber).
- ARL: SPEC-ONLY (no loop_state.json, no scripts). CONTEXT.md: ABSENT.
- Backlog (TODO.md/ROADMAP, ~53d old): P0 combat-trigger-dispatch gap, Stage 1.7 determinism, Guide attack-trigger double-fire, IzzetProwess role refactor, 8 card-handler audits from 5/09.
- Standard coverage: 4218/4218 handlers (100%, 2026-05-03). 38/38 Standard match APLs.

### mtg-meta-analyzer — ACTIVE, healthy
- Last commit `c47051f` 2026-06-21 (docs badges). Clean tree. CI green. 0 open issues.
- Recent ships: MCP server (6/11), strategy-doc-search MCP tool (code-complete 6/19), replay viewer M1-M4, MTGA live-import, command palette.
- Blocked: Pinecone live gate needs API key. Several manual GUI smoke tests pending (replay viewer M2-M4, Event Finder UX overhaul, grader chip).
- Pre-push hook: EXISTS. CONTEXT.md: ABSENT.
- Stale feature branches kept: feat/classifier-eval, feat/mcp-server, feat/replay-viewer-m1-dq.

### harness (claude-harness) — automation healthy, human-work stalled
- harness/ git (master): last human commit 2026-05-15 23:36. claude-harness-repo (public mirror): 2026-04-20, diverged from origin.
- Automation: snapshot 04:30 + drift + drift-PR running daily through 2026-06-25. ✅
- Specs: ~25 total. 2 EXECUTING stalled 1300+h (event-hub, pt-sos-handler-batch), 6-7 PROPOSED ~55d old, many UNKNOWN-status. Decision needed: execute / supersede / abandon each.
- IMPERFECTIONS.md: ~29 OPEN, file 59 days stale. (Highlights: sim-no-stack-priority, sim-no-hidden-information, affinity-never-blocks 96.9% inflated, standard-apl-goldfish-only, sim-py-hardcoded-humans-apl, several missing Modern APLs: belcher/neobrand/grixis-reanimator/temur-prowess/sultai/grixis-midrange.)
- Knowledge base: ~455 blocks, current through ~2026-06-09 (mostly auto-generated).
- HARNESS_STATUS.md: 71 days stale. CONTEXT.md + router.md: ABSENT.

### Team Resolve — not git-tracked; fresh-ish prep content
- Competitive ops hub. Handoffs through 2026-05-11 (Untapped pipeline, RC DC prep). 30+ sideboard guides.
- Pending (from handoffs): Selesnya Ouroboroid framework error, Sapling Nursery token audit, Spell Snare legality check, Lessons sub-plans for Tokyo Prowess, port playbooks to website.

### My-Website (Zuxas/TeamResolve Pages) — backburner, uncommitted batch
- GitHub Pages live. Last commit 2026-04-29. **21 modified + 22 new untracked playbooks uncommitted.** TeamResolve#1 Pages-deploy issue was self-resolved/closed (no active CI failure found).

### YT-rip — dormant utility (4 PS download scripts, last 2026-04-06). No backlog.

### claude-skills — reference library (13 cloned upstream repos, not integrated). Only 3 skills actually registered in workspace.

### Other: MTG-Math (dormant 2024), Cardtrop/Jasmine/books/guides/team-resolve-assets (dormant assets), Zuxas profile repo (active).

---

## 3. HANDOFF-04 task readiness (after verification)

| Task | Tag | Status | Note |
|---|---|---|---|
| 3.1 Install mattpocock/skills | AFK | DONE | 3 -> 13 skills (project scope). Socket/Snyk all Safe, 0 alerts. `diagnose`->`diagnosing-bugs`, router=`ask-matt`. Use per-skill `-s <name> -y` (comma-list hits interactive picker). NOT yet run: `/setup-matt-pocock-skills` (needs issue-tracker/docs choice). |
| 3.2 Git guardrails hook | HITL | DONE | `.claude/settings.json` PreToolUse + `.claude/hooks/block-dangerous-git.sh`. Bundled hook needed jq (absent) -> would fail OPEN; rewrote to Python. Verified blocks push/reset --hard/clean/branch -D/checkout ./filter-*; passes status/commit/add/diff. Active next reload. |
| 3.3 `hitl` field in loop_state.json | AFK | DONE (via ARL build) | loop_state.json created with `hitl` on queue items + loop pause-on-hitl gate. |
| 3.4 per-repo CONTEXT.md | AFK | DONE | mtg-sim, mtg-meta-analyzer, harness — grounded vocabulary. |
| 3.5 router skill | AFK | DONE | `ask-matt` upstream router installed via 3.1; no custom router.md needed. |
| 3.6 AGENTS.md Memento Principle | HITL | DONE | "THE MEMENTO PRINCIPLE" section inserted. |
| 3.7 audit claude-skills format | AFK | DONE (PASS) | All 3 installed skills have proper frontmatter; none load large context unconditionally. No changes. |

### ARL build (Deliverable A — autonomous Modern loop)
Built via 3-phase workflow. Files (mtg-sim/scripts/): arl_state, arl_generate_deck, arl_generate_apl, arl_status, arl_steer, arl_loop, arl_distill + mtg-sim/loop_state.json. Reuses harness auto_pipeline/apl_optimizer/tuning_loop/agent_hardening; Modern decks from mtg_meta.db (4080 available). Loop never commits/edits engine/, caps 200 games/matchup, Ctrl-C-safe atomic state.
Three spec deviations forced by verification: **B1** real CLI flags (`sim.py --apl/--n`; gauntlet via `parallel_launcher.py` for per-matchup JSON, not `--games`). **B2** unregistered slugs silently fall back to HumansAPL -> register-before-gauntlet + resolution guard. **B3** sequencing telemetry is NOT emitted by the engine and ARL can't touch engine/ -> `arl_distill` rescoped to gauntlet matchup JSON; full distillation logged as a P0-human blocker.

---

## 4. Recommended sequence (post-verification)

1. Run 3.1 (additive, low-risk) — DONE this session (see changelog).
2. **Re-scope section 3 with the user** before proceeding — 3.3 is blocked, 3.2's framing needs correction, ARL is a bigger decision (build vs defer).
3. Stale-state burndown candidates (independent of Pocock): triage the 6-7 PROPOSED + 2 stalled EXECUTING specs; refresh IMPERFECTIONS.md; bring harness/MEMORY.md + HARNESS_STATUS.md current; decide on mtg-sim's 36 untracked files (commit RC-prep work or archive).
4. Decide fate of original HANDOFF-04 (harness-personal private push).

---

## Changelog
- 2026-06-26: Created. Full verification sweep (4 parallel project audits + central state read).
- 2026-06-26: HANDOFF-04 section 3 executed — 3.1 (skills 3->13), 3.2 (git guardrails, jq-free rewrite), 3.4 (3x CONTEXT.md), 3.5 (ask-matt router), 3.6 (AGENTS.md Memento), 3.7 (audit PASS). ARL (Deliverable A) built for Modern incl. 3.3 hitl field; validation pending workflow completion.
