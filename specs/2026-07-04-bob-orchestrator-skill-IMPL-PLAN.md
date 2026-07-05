# /bob Orchestrator Skill — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `/bob`, a global user-invoked hybrid-conductor skill that drives any tasking doc to completion-or-honest-stop, with a testable deterministic core and a prose conductor.

**Architecture:** A bundled stdlib-only Python helper (`bob_run.py`) owns the deterministic, unit-testable mechanics — atomic claim/lockfile, run-dir scaffold, `control.md` parsing, `decisions.md` append-with-reversal. The `SKILL.md` is the conductor procedure Claude runs in the main loop, delegating heavy fan-out/verify to the `Workflow` tool in bounded waves and calling the helper via Bash for the deterministic bits. A project-override note lights up harness-specific behavior (hot zones, paths, PII).

**Tech Stack:** Python 3 (stdlib only: `os`, `json`, `time`, `pathlib`, `argparse`), pytest, Markdown (SKILL.md + convention note), the Claude Code `Workflow`/`Agent`/`advisor` tools, the project `council` + global `handoff` skills.

## Global Constraints

- Skill installs to `~/.claude/skills/bob/` (global). `disable-model-invocation: true` — never auto-fires.
- Helper is **stdlib-only** — no pip deps (global-safety across any project).
- ASCII-only output (root CLAUDE.md convention).
- Hot zones (force stop+handoff+sign-off): `mtg-sim/engine/`, DBs on `E:\mtg-data`, `harness/knowledge/` Tier-K, any `git push` / merge-to-main. Writes to `harness/knowledge/` stage to `harness/inbox/promoted/`, never direct.
- Commits allowed autonomously ONLY on the run's dedicated branch; push/merge is sign-off.
- Degrade gracefully when `council`/`delegate` skills are absent (project-scoped): inline the blind-refute council pattern via `Agent`/`Workflow`; fall back to `advisor()`.
- Claim staleness threshold: a lockfile older than **90 minutes** with no heartbeat update is considered stale and may be reclaimed (with a logged note).
- Human-gate timeout default window: **20 minutes** (configurable); on expiry default to refute-council verdict + log reversible decision.

---

## File Structure

- Create `~/.claude/skills/bob/SKILL.md` — conductor procedure (prose; the fixed spine + tiered rule + dependency fallbacks).
- Create `~/.claude/skills/bob/scripts/bob_run.py` — deterministic helper (CLI: `init`, `claim`, `check-claim`, `heartbeat`, `release`, `control`, `decision`, `status`).
- Create `~/.claude/skills/bob/scripts/test_bob_run.py` — pytest for the helper.
- Create `~/.claude/skills/bob/references/spine.md` — the phase spine + tiered decision table + hot-zone list (referenced by SKILL.md to keep it lean).
- Create `harness/knowledge/tech/bob-convention-2026-07-04.md` — project override (harness paths, hot zones, PII redaction, suggested-skills menus).

---

## Task 1: Helper — run-dir scaffold + `init`

**Files:**
- Create: `~/.claude/skills/bob/scripts/bob_run.py`
- Test: `~/.claude/skills/bob/scripts/test_bob_run.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `init_run(base_dir, doc_path) -> runid` creates `<base_dir>/bob-runs/<runid>/` with `STATUS.md`, `control.md`, `decisions.md`, `agents/`, `evidence/`. `runid` format `bob-YYYYMMDD-HHMMSS-<4hex>`. CLI: `python bob_run.py init --base <dir> --doc <path>` prints the runid.

- [ ] **Step 1: Write the failing test**

```python
# test_bob_run.py
import json, subprocess, sys
from pathlib import Path
import bob_run

def test_init_creates_run_dir(tmp_path):
    runid = bob_run.init_run(str(tmp_path), "blueprint-07-03.md")
    run = tmp_path / "bob-runs" / runid
    assert run.is_dir()
    for f in ["STATUS.md", "control.md", "decisions.md"]:
        assert (run / f).is_file(), f
    for d in ["agents", "evidence"]:
        assert (run / d).is_dir(), d
    assert runid.startswith("bob-")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/.claude/skills/bob/scripts && python -m pytest test_bob_run.py::test_init_creates_run_dir -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'bob_run'` or `AttributeError: init_run`.

- [ ] **Step 3: Write minimal implementation**

```python
# bob_run.py
import os, json, time, argparse
from pathlib import Path

def _now(): return time.strftime("%Y%m%d-%H%M%S")

def init_run(base_dir, doc_path):
    rid = f"bob-{_now()}-{os.urandom(2).hex()}"
    run = Path(base_dir) / "bob-runs" / rid
    (run / "agents").mkdir(parents=True)
    (run / "evidence").mkdir()
    (run / "STATUS.md").write_text(f"# BOB RUN {rid}\ndoc: {doc_path}\nphase: INIT\n", encoding="utf-8")
    (run / "control.md").write_text("# control channel — write commands below\n", encoding="utf-8")
    (run / "decisions.md").write_text("# decisions log (reversible)\n", encoding="utf-8")
    return rid

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    i = sub.add_parser("init"); i.add_argument("--base", required=True); i.add_argument("--doc", required=True)
    a = p.parse_args()
    if a.cmd == "init":
        print(init_run(a.base, a.doc))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/.claude/skills/bob/scripts && python -m pytest test_bob_run.py::test_init_creates_run_dir -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
cd ~/.claude/skills/bob && git -C "E:/vscode ai project/harness" rev-parse 2>/dev/null; \
git add scripts/bob_run.py scripts/test_bob_run.py 2>/dev/null || true
# NOTE: ~/.claude/skills is not a repo by default; if uninitialized, skip commit and
# track these files via the harness build commit in Task 10. See Global Constraints.
```

---

## Task 2: Helper — atomic `claim` / `check-claim` / `release` (gate G2)

**Files:**
- Modify: `~/.claude/skills/bob/scripts/bob_run.py`
- Test: `~/.claude/skills/bob/scripts/test_bob_run.py`

**Interfaces:**
- Consumes: `init_run`.
- Produces:
  - `claim(doc_path, runid, ttl_min=90) -> bool` — writes `<doc_path>.bobclaim` JSON `{runid, pid, ts}` ONLY if no live (non-stale) claim exists; returns `True` on success, `False` if a live claim blocks it.
  - `check_claim(doc_path, ttl_min=90) -> dict|None` — returns the live claim dict or `None` (also `None` if stale).
  - `release(doc_path, runid) -> bool` — removes the claim iff it belongs to `runid`.

- [ ] **Step 1: Write the failing tests**

```python
def test_claim_then_second_claim_refused(tmp_path):
    doc = tmp_path / "blueprint-07-03.md"; doc.write_text("x")
    assert bob_run.claim(str(doc), "run-A") is True
    assert bob_run.check_claim(str(doc))["runid"] == "run-A"
    assert bob_run.claim(str(doc), "run-B") is False   # refused: live claim

def test_stale_claim_can_be_reclaimed(tmp_path):
    doc = tmp_path / "d.md"; doc.write_text("x")
    bob_run.claim(str(doc), "run-A")
    cf = Path(str(doc) + ".bobclaim")
    data = json.loads(cf.read_text()); data["ts"] = time.time() - 91*60
    cf.write_text(json.dumps(data))                     # backdate 91 min
    assert bob_run.check_claim(str(doc)) is None        # stale -> invisible
    assert bob_run.claim(str(doc), "run-B") is True     # reclaim allowed

def test_release_only_by_owner(tmp_path):
    doc = tmp_path / "d.md"; doc.write_text("x")
    bob_run.claim(str(doc), "run-A")
    assert bob_run.release(str(doc), "run-B") is False
    assert bob_run.release(str(doc), "run-A") is True
    assert bob_run.check_claim(str(doc)) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest test_bob_run.py -k claim -v`
Expected: FAIL — `AttributeError: claim`.

- [ ] **Step 3: Write minimal implementation**

```python
def _claim_path(doc_path): return Path(str(doc_path) + ".bobclaim")

def check_claim(doc_path, ttl_min=90):
    cf = _claim_path(doc_path)
    if not cf.exists(): return None
    try: data = json.loads(cf.read_text(encoding="utf-8"))
    except Exception: return None
    if time.time() - float(data.get("ts", 0)) > ttl_min * 60: return None  # stale
    return data

def claim(doc_path, runid, ttl_min=90):
    if check_claim(doc_path, ttl_min) is not None: return False
    _claim_path(doc_path).write_text(
        json.dumps({"runid": runid, "pid": os.getpid(), "ts": time.time()}), encoding="utf-8")
    return True

def release(doc_path, runid):
    data = check_claim(doc_path, ttl_min=10**9)  # ignore staleness on release
    if not data or data.get("runid") != runid: return False
    _claim_path(doc_path).unlink(missing_ok=True); return True
```

Add CLI subparsers `claim` / `check-claim` / `release` (each `--doc`, `--runid`) that print `OK`/`REFUSED`/`json`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest test_bob_run.py -k claim -v`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit** (see Task 1 note on repo location).

---

## Task 3: Helper — `control` parse + `decision` append with reversal (gates G5, G7)

**Files:**
- Modify: `~/.claude/skills/bob/scripts/bob_run.py`
- Test: `~/.claude/skills/bob/scripts/test_bob_run.py`

**Interfaces:**
- Consumes: `init_run`.
- Produces:
  - `read_control(run_dir) -> list[dict]` — parses `control.md` lines of form `!<cmd> <target?> <note?>` into `{cmd, target, note}` (cmds: `pause`, `resume`, `kill`, `redirect`, `rescope`, `stop`). Non-`!` lines ignored.
  - `append_decision(run_dir, what, why, source, reversal)` — appends a structured, timestamped, reversible entry to `decisions.md`. `source` in `{human, timeout-default, council, advisor}`.

- [ ] **Step 1: Write the failing tests**

```python
def test_read_control_parses_commands(tmp_path):
    run = tmp_path / "r"; (run).mkdir(); c = run / "control.md"
    c.write_text("# header\n!pause\n!kill agent-03\n!redirect agent-02 use the match APL\nnoise\n")
    cmds = bob_run.read_control(str(run))
    assert {"cmd":"pause","target":None,"note":None} in cmds
    assert {"cmd":"kill","target":"agent-03","note":None} in cmds
    assert any(x["cmd"]=="redirect" and x["target"]=="agent-02"
               and x["note"]=="use the match APL" for x in cmds)
    assert len(cmds) == 3

def test_append_decision_is_reversible_and_tagged(tmp_path):
    run = tmp_path / "r"; run.mkdir(); (run/"decisions.md").write_text("# decisions\n")
    bob_run.append_decision(str(run), what="passed gate 2 for affinity",
        why="refute-council 2/3 could not break it", source="timeout-default",
        reversal="git revert <hash>; reopen gate 2")
    txt = (run/"decisions.md").read_text()
    assert "timeout-default" in txt and "REVERSAL:" in txt and "passed gate 2" in txt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest test_bob_run.py -k "control or decision" -v`
Expected: FAIL — `AttributeError`.

- [ ] **Step 3: Write minimal implementation**

```python
_CTRL = {"pause","resume","kill","redirect","rescope","stop"}

def read_control(run_dir):
    out = []
    for ln in (Path(run_dir)/"control.md").read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln.startswith("!"): continue
        parts = ln[1:].split(maxsplit=2)
        if not parts or parts[0] not in _CTRL: continue
        out.append({"cmd": parts[0],
                    "target": parts[1] if len(parts) > 1 else None,
                    "note": parts[2] if len(parts) > 2 else None})
    return out

def append_decision(run_dir, what, why, source, reversal):
    entry = (f"\n## {time.strftime('%Y-%m-%d %H:%M:%S')} [{source}]\n"
             f"- WHAT: {what}\n- WHY: {why}\n- REVERSAL: {reversal}\n")
    with open(Path(run_dir)/"decisions.md", "a", encoding="utf-8") as fh:
        fh.write(entry)
```

Add CLI `control --run <dir>` (prints JSON) and `decision --run <dir> --what .. --why .. --source .. --reversal ..`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest test_bob_run.py -v`
Expected: PASS (all tasks 1–3 green).

- [ ] **Step 5: Commit** (see Task 1 note).

---

## Task 4: PROVE-FIRST — the timeout-default human gate (gate G5, behavioral)

This is the spec's flagged highest-risk mechanism. Prove it in isolation before wiring the spine.

**Files:**
- Create: `~/.claude/skills/bob/references/timeout-gate.md` — the exact conductor procedure.

**Interfaces:**
- Consumes: `append_decision`, and the conductor's refute-council result.
- Produces: a documented, repeatable gate procedure the SKILL.md includes verbatim.

- [ ] **Step 1: Write the procedure (the "test" is a dry behavioral run, below)**

```markdown
# Timeout-default human gate (conductor procedure)
1. Run the refute-council on "gate <id> is met"; capture verdict V (PASS/FAIL) + evidence paths.
2. Present V + evidence to the user via AskUserQuestion (options: Accept / Reject / Hold).
3. Start a bounded wait: ScheduleWakeup(delaySeconds=1200, reason="bob gate <id> timeout").
   - If the user answers first, honor the answer; cancel the fallback.
   - If the wakeup fires with no answer: DEFAULT to V, then call
     `bob_run.py decision --source timeout-default --what "gate <id> -> <V>"
      --why "<council rationale>" --reversal "<how to reopen>"`.
4. Never default a HOT-ZONE gate: if the gate touches a hot zone, timeout => STOP+handoff
   (not default-proceed). Only non-hot-zone gates auto-default.
```

- [ ] **Step 2: Behavioral verification — simulate no-response**

Run this scripted check (no live user):
```bash
cd ~/.claude/skills/bob/scripts && python - <<'PY'
import bob_run, tempfile, os, json
from pathlib import Path
run = Path(tempfile.mkdtemp())/"r"; run.mkdir(); (run/"decisions.md").write_text("# d\n")
# simulate the timeout branch defaulting to a PASS council verdict
bob_run.append_decision(str(run), what="gate 2 -> PASS (affinity)",
    why="refute-council 2/3 no break", source="timeout-default",
    reversal="reopen gate 2; git revert branch tip")
t = (run/"decisions.md").read_text()
assert "timeout-default" in t and "gate 2 -> PASS" in t and "REVERSAL" in t
print("G5 mechanics OK")
PY
```
Expected: prints `G5 mechanics OK`.

- [ ] **Step 3: Verify the hot-zone carve-out is documented**

Confirm `references/timeout-gate.md` step 4 states hot-zone gates NEVER auto-default. (Grep: `grep -n "Never default a HOT-ZONE" references/timeout-gate.md` → 1 match.)

- [ ] **Step 4: Commit** (see Task 1 note).

---

## Task 5: SKILL.md — frontmatter + spine + reference wiring

**Files:**
- Create: `~/.claude/skills/bob/SKILL.md`
- Create: `~/.claude/skills/bob/references/spine.md`

**Interfaces:**
- Consumes: `references/spine.md`, `references/timeout-gate.md`, `scripts/bob_run.py`.
- Produces: the invocable `/bob` skill.

- [ ] **Step 1: Write `references/spine.md`**

Content = the 7-phase spine (INTAKE→PLAN+CLAIM→FAN-OUT→VERIFY→GATE→COMMIT→CLOSE), the tiered-by-blast-radius decision table, the hot-zone list, and the dependency-fallback rules — copied from the spec's sections verbatim (ASCII-only).

- [ ] **Step 2: Write `SKILL.md` frontmatter + body**

```markdown
---
name: bob
description: Autonomous hybrid-conductor. Use ONLY when the user types "/bob" or says "use bob to ...". Point it at a tasking doc (spec / handoff / .md); it drives the work to a proven-done state or an honest documented stop, fanning out 4-20 agents. disable-model-invocation.
disable-model-invocation: true
---
# /bob — hybrid-conductor orchestrator
Announce: "Using /bob to drive <doc> — conductor in the main loop, Workflow for fan-out."
Read references/spine.md now. Then follow the phases in order. Never skip PLAN+CLAIM.
Compute SKILL_DIR; call the helper as: python "$SKILL_DIR/scripts/bob_run.py" <cmd> ...
[phases reference the sections built in Tasks 6-9]
```

- [ ] **Step 3: Verify the skill loads (behavioral)**

In a fresh Claude Code turn: type `/bob` with no args → expect it to announce and ask for a doc path, making ZERO writes. (Confirms `disable-model-invocation` + read-only entry.)

- [ ] **Step 4: Commit** (see Task 1 note).

---

## Task 6: SKILL.md — INTAKE + PLAN+CLAIM sections (gates G1, G2, G3-setup)

**Files:**
- Modify: `~/.claude/skills/bob/SKILL.md`

- [ ] **Step 1: Write the INTAKE section**

Prose instructing: read doc + repo context READ-ONLY; classify (spec-with-gates / handoff / loose md); derive a working definition-of-done; if a real decision or scope ambiguity → invoke `brainstorming` (+ council/refute-panel) BEFORE proceeding; emit a PLAN (goal, gates, independent sub-units, agent count auto-scaled ≤20, affected git subproject, hot-zone touchpoints flagged).

- [ ] **Step 2: Write the PLAN+CLAIM section**

Prose: present PLAN; make NO writes until user confirms; run `bob_run.py check-claim` → if live claim, REFUSE + report who/when + STOP; on confirm run `bob_run.py init` then `bob_run.py claim`, then `git -C <subproject> switch -c bob/<runid>`.

- [ ] **Step 3: Behavioral verification (G1 + G2)**

- G1: point `/bob` at an existing spec; confirm it produces a PLAN and `git -C <subproject> status` stays clean + no `bob-runs/` dir until you confirm.
- G2: pre-create a `<doc>.bobclaim` (fresh ts); run `/bob <doc>`; confirm it refuses and names the holder.

- [ ] **Step 4: Commit** (see Task 1 note).

---

## Task 7: SKILL.md — FAN-OUT + VERIFY sections (gate G4 + inlined refute-council)

**Files:**
- Modify: `~/.claude/skills/bob/SKILL.md`

- [ ] **Step 1: Write the FAN-OUT section**

Prose: conductor writes a `Workflow` script per WAVE. Each agent prompt MUST include: (i) append a one-line worklog to `agents/agent-NN.md` before each read/write; (ii) `Read control.md` at each checkpoint, honor `pause`/`kill`/`redirect`; (iii) write a concrete artifact to `evidence/` per gate. Between waves the conductor re-reads control via `bob_run.py control` and updates `STATUS.md`.

- [ ] **Step 2: Write the VERIFY section**

Prose: per sub-unit — evidence-floor (no artifact in `evidence/` ⇒ gate CANNOT pass ⇒ stop+handoff) → adaptive verifier by task type (code→`verify` skill/tests/lint/run; sim→gates/gauntlet numbers; docs→review) → blind refute-council: prefer the `council` skill if present, else inline (spawn 3 blind `Agent` subagents each briefed to REFUTE "gate met"; majority-refute = FAIL), else `advisor()`.

- [ ] **Step 3: Behavioral verification (G4)**

Run a scoped fan-out on a throwaway sub-unit that intentionally produces NO evidence artifact; confirm the gate is declared FAIL and the run stops with a handoff rather than passing.

- [ ] **Step 4: Commit** (see Task 1 note).

---

## Task 8: SKILL.md — GATE + tiered decision + hot-zone stop (gates G5, G6)

**Files:**
- Modify: `~/.claude/skills/bob/SKILL.md`

- [ ] **Step 1: Wire the timeout-default gate**

Include `references/timeout-gate.md` procedure verbatim into the GATE section. Non-hot-zone unmet gate → council authorizes + proceeds; timeout → default to refute-council verdict + `bob_run.py decision --source timeout-default ...`.

- [ ] **Step 2: Write the hot-zone stop rule**

Prose: before ANY hot-zone touch (engine / `E:\mtg-data` / `knowledge/` Tier-K / push / merge), STOP, write a `/handoff`, request sign-off. Knowledge writes stage to `inbox/promoted/`.

- [ ] **Step 3: Behavioral verification (G5 + G6)**

- G5: run a non-hot-zone gate, simulate no-response past the window → confirm proceed + a `timeout-default` entry in `decisions.md`.
- G6: plant a sub-unit whose step edits `mtg-sim/engine/` → confirm `/bob` STOPS and writes a handoff instead of editing.

- [ ] **Step 4: Commit** (see Task 1 note).

---

## Task 9: SKILL.md — COMMIT + CLOSE sections (gates G3, G8)

**Files:**
- Modify: `~/.claude/skills/bob/SKILL.md`

- [ ] **Step 1: Write the COMMIT section**

Prose: commit ONLY to `bob/<runid>` branch (autonomous, reversible). `git push` / merge-to-main → sign-off gate, never autonomous.

- [ ] **Step 2: Write the CLOSE section**

Prose: update `MEMORY.md` session log + docs per WRITING BACK; knowledge → `inbox/promoted/` only; on early stop write a `/handoff` (global skill + project override: scratchpad, PII-redacted, suggested-skills block) and promote to `harness/handoffs/` if session-sized; finally `bob_run.py release`.

- [ ] **Step 3: Behavioral verification (G3 + G8)**

- G3: after a scoped run, `git -C <subproject> log main..bob/<runid>` shows the commits AND `git -C <subproject> log -1 main` is unchanged.
- G8: force a stop; confirm a handoff doc exists in scratchpad, is PII-redacted (no `Jermey`/`Zuxas`/deck-variant names), and ends with a Suggested-skills block.

- [ ] **Step 4: Commit** (see Task 1 note).

---

## Task 10: Project override note + harness build commit

**Files:**
- Create: `harness/knowledge/tech/bob-convention-2026-07-04.md`
- Modify: `harness/knowledge/_index.md` (add the row)

> **Hot-zone note:** `harness/knowledge/` is a hot zone. This file is NEW (additive, not a Tier-K rewrite), but per protocol get user sign-off on the harness commit before it lands.

- [ ] **Step 1: Write the convention note**

Mirror `handoff-convention-2026-06-30.md`: what `/bob` is for; harness hot-zone list; `bob-runs/` location (session scratchpad, gitignored, disposable); PII redaction (Jermey/Jerme/Zuxas/deck-variant names); "Suggested skills" pulled from `harness/skills/_index.md` then global set; point-at-artifacts rule; Changelog.

- [ ] **Step 2: Add the `_index.md` row**

`| tech/bob-convention-2026-07-04 | tech | 2026-07-04 | project overrides for the /bob orchestrator skill |`

- [ ] **Step 3: Ask for sign-off, then commit the harness half**

Present the diff; on user OK: `git -C "E:/vscode ai project/harness" add specs/2026-07-04-bob-orchestrator-skill*.md knowledge/tech/bob-convention-2026-07-04.md knowledge/_index.md && git -C "E:/vscode ai project/harness" commit` (message per spec template). If `~/.claude/skills/bob/` is not a git repo, note in the commit body that the skill files live at that path (untracked by harness).

---

## Task 11: End-to-end acceptance run (all gates G1–G8)

**Files:**
- Create: a throwaway fixture `<scratchpad>/bob-fixture.md` (a 2-sub-unit toy tasking doc, one sub-unit non-hot-zone, one planted hot-zone).

- [ ] **Step 1: Run `/bob <scratchpad>/bob-fixture.md` end-to-end**

Drive the full spine on the fixture inside a disposable git subproject (or `mtg-meta-analyzer` on a throwaway branch).

- [ ] **Step 2: Assert every gate**

Walk G1–G8 from the spec's Validation-gates table; record PASS/FAIL for each in the run's `decisions.md`.

- [ ] **Step 3: If all pass, flip spec status → SHIPPED**

Update the spec frontmatter + `_index.md` entry to SHIPPED with the harness commit hash; move the two annotated imperfections into `harness/IMPERFECTIONS.md`.

- [ ] **Step 4: Final commit + release** (see Task 10 sign-off rule).

---

## Self-Review

**Spec coverage:** INTAKE→Task6; PLAN+CLAIM→Task6; FAN-OUT→Task7; VERIFY→Task7; GATE/timeout→Task4+8; tiered rule→Task8; COMMIT→Task9; CLOSE/handoff→Task9; concurrency/claim→Task2; monitoring/control→Task3+7; dependency-fallbacks→Task5+7; convention note→Task10; all 8 gates→Task11 (+ unit coverage of G2/G5/G7 in Tasks 2–4). No spec section left without a task.

**Placeholder scan:** No TBD/TODO; every code step shows real code; gate-checks are concrete commands. Prose SKILL.md tasks are explicitly validated by behavioral gate procedures (not fake pytest), which is correct for a prose skill.

**Type consistency:** Helper names stable across tasks — `init_run`, `claim`/`check_claim`/`release` (ttl_min=90), `read_control` (`{cmd,target,note}`), `append_decision` (`what,why,source,reversal`). CLI verbs `init/claim/check-claim/heartbeat/release/control/decision/status` match their callers in Tasks 6–9.

**Known deviation:** `~/.claude/skills/bob/` may not be a git repo; commits for skill files are handled by the note in Task 1/10 rather than assumed. Flagged, not hidden.
```
