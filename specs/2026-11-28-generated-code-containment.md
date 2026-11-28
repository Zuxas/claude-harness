---
title: "Generated-code containment: honest isolation posture + declarative-APL migration"
status: "PROPOSED"
created: "2026-11-28"
updated: "2026-11-28"
project: "harness"
estimated_time: "design doc + follow-up issues (no code in this deliverable)"
related_findings: []
related_commits: []
supersedes: null
superseded_by: null
---

# Generated-code containment (follow-up to #2 / PR #38, closes #39's doc path)

## Goal

Issue #39 asks to *fully* contain execution of model-generated APLs, and offers
two acceptance paths: (A) a test proving the smoke child cannot open a socket or
write outside its scratch dir, or (B) **a design doc + issues for the
declarative-APL migration**. This spec is path B. It records what isolation #2
actually shipped, the audit #39 item 2 requested, what a real OS boundary would
cost on *this* machine, and the two follow-up issues that carry the real fixes.

It deliberately does **not** build a Windows sandbox and call it a security
boundary — see Options A/B for why that would be dishonest here.

## Current isolation (what #2 / PR #38 shipped)

`auto_pipeline._smoke_test_apl` runs a generated APL out-of-process:
- **AST allowlist before write** (`_ALLOWED_IMPORT_ROOTS` + `_BANNED_CALLS` for
  `eval`/`exec`/`compile`/`__import__`/`open`). Allowlist, not denylist.
- **`python -I` subprocess** (`_apl_smoke_runner.py`): cwd and the script dir are
  off `sys.path`, so a planted module can't shadow the real engine.
- **Scrubbed env** (`_child_env`, `_CHILD_ENV_KEEP` allowlist): no
  `ANTHROPIC_API_KEY`, OAuth, or GH creds reach the child.
- **Timeout** (`_SMOKE_TIMEOUT`).

This is real process + credential isolation. It is **not** a kernel/OS sandbox:
the child runs as the same OS user, keeping that user's filesystem and network
rights. An AST allowlist also cannot catch every dynamic reach (getattr tricks).
`python -I` + scrubbed env is a blast-radius reducer, **not** a security boundary.

## Threat model (why this is P1 but bounded)

The pipeline runs on the operator's own Windows box, on inputs the operator's
own Gemma produces from the operator's meta data — not on externally supplied
untrusted input. The live risk is **defence-in-depth against pathological model
output** (a hallucinated `os.system`, an obfuscated exfil), not an active remote
attacker. #39 itself states the operative control: *"keep generating/validating
only under the operator's own machine, not unattended on untrusted input."* That
constraint is the real boundary today; everything below hardens it.

## Audit (#39 item 2): every in-process load of generated APL code

Grep of `agents/scripts/` for `importlib` / `spec_from_file_location` /
`import_module` of generated or arbitrary APL modules:

| Site | In-process? | Gated? | Notes |
|---|---|---|---|
| `auto_pipeline._smoke_test_apl` | No (subprocess) | **Yes** | AST + `-I` + scrubbed env + timeout. The reference. |
| `gemma_apl_factory.validate_apl_code` | **Yes** | **No** | `compile()` + writes `apl/_temp_generated.py` + `import_module` + instantiates + runs 100 games, all in a process that holds secrets. No AST gate, no env scrub. **This is the gap.** |
| `apl_optimizer.load_apl_from_file` | **Yes** | No | `spec_from_file_location` exec of whatever APL path is passed; runs in-process. Operates on human + auto APLs. |
| `apl_grinder.load_apl_from_file` | **Yes** | No | Same pattern as the optimizer. |
| `matchup_gauntlet.load_apl_for_deck` | **Yes** | No | `import_module` of APL modules. The gauntlet itself runs in **mtg-sim**, a separate trust boundary (documented, acceptable); `calibrate.py` calls it harness-side. |

**Finding:** `auto_pipeline` is gated, but `gemma_apl_factory` imports
model-written code directly into a secret-holding process with no gate at all —
a strictly worse exposure than the path #2 fixed. The optimizer/grinder exec any
APL file in-process by design (they mutate and re-sim human APLs); they become a
generated-code path only when pointed at `apl/auto_apls/*`.

## Containment options

**A. Windows-native OS sandbox (AppContainer / Job Object).** A Job Object caps
resources and lets you kill the tree, but does **not** by itself deny network or
filesystem writes. A true AppContainer (capability-scoped FS/network) is a real
boundary but a large, fragile, Windows-only build with **no PowerShell/Windows
CI** to prove it — exactly the thing #39 warns against calling a boundary without
a falsifiable test. Not recommended as the primary fix.

**B. Linux sandbox (bubblewrap/seccomp/`unshare`) via WSL or a container.**
The clean way to get the #39-A acceptance test (socket-denied + write-outside-
scratch-denied). **Verified unavailable on the box (2026-11-28):** `wsl.exe`
reports WSL not installed (no distro), and Docker is absent. Viable only if the
pipeline is moved into a Linux container/runtime — a deployment change, not a
code change.

**C. Declarative, non-executable APLs interpreted by trusted engine code**
(Tom's preferred). Generated output becomes data (a validated APL schema) that
trusted mtg-sim code interprets; model output never executes. **Removes the
class entirely.** Cost: an APL schema + interpreter in mtg-sim.

## Recommendation

1. **Near-term, cheap, real (harness):** close the audit gap — route
   `gemma_apl_factory.validate_apl_code` through the same AST gate +
   `_apl_smoke_runner` subprocess `auto_pipeline` already uses, so no path
   imports model code into a secret-holding process. Keep the operator-machine-
   only posture explicit in the pipeline docstring.
2. **Long-term, class-removing (mtg-sim):** the declarative-APL migration (C).
3. **Defer A** unless/until the pipeline must run on untrusted input or
   unattended on a shared host; if it ever does, B (containerize) beats A.

## Follow-up issues

- **(harness)** Gate `gemma_apl_factory` in-process import — route through the
  AST allowlist + `_apl_smoke_runner` subprocess. Small, independently testable.
- **(mtg-sim)** Declarative-APL schema + interpreter epic (Option C) — the real
  fix that removes executable model output.

## Acceptance (#39)

Satisfies #39's path B ("a design doc + issues for the declarative-APL
migration"). #39 should stay **open** tracking the declarative epic, or close in
favour of the two follow-up issues — operator/Tom's call. `python -I` +
scrubbed-env remains documented as a blast-radius reducer, not a boundary.
