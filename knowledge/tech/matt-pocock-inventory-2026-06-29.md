# Matt Pocock Skills + Repos -- Vetting & Global-Install Plan (2026-06-29)

Source repo: https://github.com/mattpocock/skills (MIT, Claude Code plugin, default branch main).
Method: verified against live GitHub on 2026-06-29 via the tree API (HEAD recursive),
raw.githubusercontent.com SKILL.md frontmatter, the repo metadata endpoint, and WebSearch.
All output ASCII; '->' denotes flow/mapping.

Repo shape (live tree): 36 SKILL.md files across 6 folders under skills/ ->
engineering 14, productivity 5, misc 4, personal 2, in-progress 7, deprecated 4.
Excluding in-progress (7) + deprecated (4) leaves 25 active/shipped skills.

---

## 0. CORRECT GLOBAL INSTALL METHOD (load-bearing -- read first)

GOAL: place vetted skills in C:/Users/jerme/.claude/skills so EVERY new project
inherits them automatically.

VERIFIED ON THIS MACHINE (2026-06-29):
- `npx skills add ...` DEFAULTS TO PROJECT SCOPE. Proof: every Matt Pocock skill
  currently available in-session (diagnosing-bugs, grill-me, tdd, handoff,
  improve-codebase-architecture, grill-with-docs, git-guardrails-claude-code, etc.)
  lives in `E:/vscode ai project/.claude/skills/`, NOT in `~/.claude/skills/`.
  A plain `npx skills add` will NOT make a skill available to a different project.
- `~/.claude/skills/` currently holds ONLY one hand-placed folder
  (auto-github-contributor). Global skills work by being a folder-with-SKILL.md there.
- Global PLUGINS are wired differently: superpowers is installed at `scope: user`
  in `~/.claude/plugins/...` and enabled via `enabledPlugins` in
  `~/.claude/settings.json`. That is the only confirmed user-scope inheritance path.

CONCLUSION ON THE `-g` FLAG:
- The per-skill evals quote `npx skills@latest add <skill> -g -a claude-code`. The
  `-g`/`--global` flag is UNVERIFIED on this win32 box -- do not assume it lands in
  `~/.claude/skills`. If you use it, VERIFY the target dir afterward; if it wrote to
  the project, fall back to the hand-place method below.

GLOBAL FALLBACK (RECOMMENDED, reliable, matches how auto-github-contributor is wired):
  hand-place each vetted skill folder (containing SKILL.md) into
  C:/Users/jerme/.claude/skills/<name>/ . New projects auto-inherit ~/.claude/skills/*.
  Because the vetted skills are already downloaded into the project copy, the cheapest
  global install for an ALREADY-LOCAL skill is a copy-up:
    cp -r "E:/vscode ai project/.claude/skills/<name>" "C:/Users/jerme/.claude/skills/"
  For a skill NOT yet local: fetch into the project first, then move up:
    npx skills@latest add mattpocock/skills/engineering/<name>
    cp -r "E:/vscode ai project/.claude/skills/<name>" "C:/Users/jerme/.claude/skills/"

WHOLE-SUITE ALTERNATIVE (user scope, like superpowers -- but pulls ALL 36 incl.
deprecated/in-progress, so NOT preferred for a cherry-picked set):
    claude plugin marketplace add mattpocock/skills
    claude plugin install skills@mattpocock

SUMMARY: prefer the hand-place / copy-up method into C:/Users/jerme/.claude/skills.
Treat `-g` as a convenience to be verified, not trusted.

---

## 1. GLOBAL-INSTALL LIST (vetted -> ~/.claude/skills)

Legend: [local] = already downloaded under E:/vscode ai project/.claude/skills
(copy-up is the install). [fetch] = not local yet (fetch then move up).

ENGINEERING
- codebase-design [fetch] -- Shared design vocabulary (depth, seam, adapter, deletion
  test) for deep modules; language-agnostic, pairs with improve-codebase-architecture;
  applies to mtg-sim engine/APL/ARL refactors and harness module boundaries.
    npx skills@latest add mattpocock/skills/engineering/codebase-design
    cp -r "E:/vscode ai project/.claude/skills/codebase-design" "C:/Users/jerme/.claude/skills/"

- diagnosing-bugs [local] -- Language-agnostic six-phase debug loop; build a tight
  pass/fail repro BEFORE editing. Already present in-session.
    cp -r "E:/vscode ai project/.claude/skills/diagnosing-bugs" "C:/Users/jerme/.claude/skills/"

- domain-modeling [fetch] -- Maintains /CONTEXT.md glossary + docs/adr/ ADRs, challenges
  imprecise terms vs code; live successor to deprecated ubiquitous-language. High value
  for mtg-sim domain vocab (archetypes, APLs, gauntlets, ARL) and harness spec terms.
    npx skills@latest add mattpocock/skills/engineering/domain-modeling
    cp -r "E:/vscode ai project/.claude/skills/domain-modeling" "C:/Users/jerme/.claude/skills/"

- grill-with-docs [local] -- Plan/design interview that emits ADRs + glossary as it goes;
  builds on grilling + domain-modeling. Captures decisions as durable docs. Install
  alongside domain-modeling so ADR/glossary outputs land correctly.
    cp -r "E:/vscode ai project/.claude/skills/grill-with-docs" "C:/Users/jerme/.claude/skills/"

- improve-codebase-architecture [local] -- "Deepen shallow modules for testability + AI
  navigability"; explore + HTML-report phases run on any Python repo. Final phase invokes
  /grilling and reads a CONTEXT.md, so install grilling alongside.
    cp -r "E:/vscode ai project/.claude/skills/improve-codebase-architecture" "C:/Users/jerme/.claude/skills/"

- prototype [fetch] -- Build a throwaway prototype to answer a design question, then
  delete or fold in. Useful for validating an mtg-sim state-model question
  (priority/combat/stack) in a disposable app before touching the real engine.
    npx skills@latest add mattpocock/skills/engineering/prototype
    cp -r "E:/vscode ai project/.claude/skills/prototype" "C:/Users/jerme/.claude/skills/"

- resolving-merge-conflicts [fetch] -- Language-agnostic git merge/rebase workflow
  (assess history -> read context -> resolve preserving both intents -> typecheck/test/
  format -> commit). Runs the project's own validation, so adapts to pytest/ruff. Useful
  in mtg-sim, mtg-meta-analyzer, My-Website (sibling repos are git; harness root is not).
    npx skills@latest add mattpocock/skills/engineering/resolving-merge-conflicts
    cp -r "E:/vscode ai project/.claude/skills/resolving-merge-conflicts" "C:/Users/jerme/.claude/skills/"

- tdd [local] -- Red-green-refactor via vertical tracer-bullet slices, testing behavior
  through public interfaces; maps to pytest for mtg-sim card handlers (pairs with
  next-card) and meta-analyzer retrieval. Overlaps superpowers:test-driven-development
  (preference, not conflict).
    cp -r "E:/vscode ai project/.claude/skills/tdd" "C:/Users/jerme/.claude/skills/"

PRODUCTIVITY
- grilling [fetch] -- The reusable engine: one-question-at-a-time, walk-the-design-tree,
  recommend-an-answer, explore-codebase-instead-of-asking. Highest-leverage of the set;
  design-before-build applies to every repo. MUST be global because grill-me, grill-with-docs
  and improve-codebase-architecture depend on it.
    npx skills@latest add mattpocock/skills/productivity/grilling
    cp -r "E:/vscode ai project/.claude/skills/grilling" "C:/Users/jerme/.claude/skills/"

- grill-me [local] -- Thin user-invoked wrapper that fires the /grilling loop; pre-build
  gate on any repo. Install alongside grilling. (Already in-session -- confirm not shadowed.)
    cp -r "E:/vscode ai project/.claude/skills/grill-me" "C:/Users/jerme/.claude/skills/"

- handoff [local] -- Compacts a conversation into a portable handoff doc (decisions,
  suggested-skills, artifact refs, secret redaction). Fits the harness multi-agent ARL
  loop; complements MEMORY.md. Caveat: writes to %TEMP% by default -- point it at our
  scratchpad/MEMORY.md paths in practice.
    cp -r "E:/vscode ai project/.claude/skills/handoff" "C:/Users/jerme/.claude/skills/"

- writing-great-skills [fetch] -- Reference for skill-authoring vocabulary (predictability,
  invocation types, information hierarchy, leading words, progressive disclosure) and failure
  modes (premature completion, sediment, sprawl, no-ops). We maintain a skills/ tree and edit
  skills constantly -- raises quality of every skill we author.
    npx skills@latest add mattpocock/skills/engineering/writing-great-skills
    cp -r "E:/vscode ai project/.claude/skills/writing-great-skills" "C:/Users/jerme/.claude/skills/"

MISC
- git-guardrails-claude-code [local] -- PreToolUse hook hard-blocking destructive git
  (push/force-push, reset --hard, clean, branch -D, checkout/restore). Blanket safety net;
  matches our commit/push-discipline feedback. Hook is a bash script -> runs via Git Bash
  on this Windows box (available). Already in-session: verify ~/.claude/settings.json hook
  registration before treating as global (hook config, not just the skill folder, must exist).
    cp -r "E:/vscode ai project/.claude/skills/git-guardrails-claude-code" "C:/Users/jerme/.claude/skills/"

PERSONAL (treat opinionated defaults as defaults, not gospel)
- edit-article [fetch] -- Long-form prose editor: dependency DAG of sections -> confirm
  structure -> tighten each under a 240-char/paragraph cap. Useful for My-Website playbooks
  and MTG meta reports, and any README/docs. User-invoked = zero context cost until called;
  the 240-char cap is easy to relax.
    npx skills@latest add mattpocock/skills/personal/edit-article
    cp -r "E:/vscode ai project/.claude/skills/edit-article" "C:/Users/jerme/.claude/skills/"

IN-PROGRESS (valuable but UNSTABLE; in-progress folder is excluded by suite installers,
so these almost certainly require manual fetch/copy. Verify before relying.)
- decision-mapping [fetch/manual] -- markdown + git: turns a loose idea into git-tracked
  Research/Prototype/Grilling tickets, resolves one per session, hands off. Near-exact match
  for the ARL loop + IMPERFECTIONS ledger. Depends on grilling/domain-modeling/prototype --
  install the set.
    npx skills@latest add mattpocock/skills  # select decision-mapping; then copy folder to ~/.claude/skills

- loop-me [fetch/manual] -- Grills the user into workflows/*.md automation specs
  (trigger/checkpoint/push-right/brief). Fits spec'ing the mtg-sim ARL gauntlet loops and
  meta-analyzer scrape schedules. Overlaps grill-me/grilling and harness conventions.
    npx skills@latest add mattpocock/skills  # select loop-me; then copy folder to ~/.claude/skills

- review [fetch/manual] -- Two-axis diff review (Standards vs Spec) in parallel sub-agents
  over `git diff <point>...HEAD`. Complements /code-review and /review (those don't separate
  spec-fidelity from standards). Degrades gracefully when docs/agents/issue-tracker.md absent.
    npx skills@latest add mattpocock/skills  # select review; then copy folder to ~/.claude/skills

---

## 2. PROJECT-ONLY (scope to a specific repo, not global)

- setup-matt-pocock-skills -> any repo that ADOPTS the tracker workflow. One-time per-repo
  bootstrapper (issue tracker config, 5-state triage labels, docs/agents/ layout, writes
  CLAUDE.md/AGENTS.md). disable-model-invocation:true. No standing global value.
- to-issues -> a future GitHub-hosted/tracker-based repo. Sound vertical-slice methodology,
  but it PUBLISHES to a tracker using setup-matt-pocock-skills labels; our solo/local-Python
  repos use an IMPERFECTIONS ledger, not GitHub Issues.
- writing-beats -> My-Website (and meta-analyzer report write-ups). Long-form prose authoring
  (ground each concept before later beats depend on it). Irrelevant to sim engine/harness.

---

## 3. STUDY-PATTERN (port the idea into our stack; do not install)

Featured (the four called out):
- evalite -> apl_judge. TS/Vitest-only, NOT installable. Validates apl_judge's shape
  (file-based eval cases + scorer/grader fns + localhost trend UI). PORT TARGET: keep
  apl_judge; borrow watch-mode + per-case scorer + trend-UI. Python drop-ins if we want a
  full framework: Inspect AI (UK AISI) or DeepEval; lightweight = pytest + a scorer-model
  fixture.
- Ralph loop (Geoffrey Huntley's original; Matt Pocock popularized variant -- NOT a
  mattpocock repo) -> the harness ARL. Run a coding agent on a clean slate repeatedly; state
  lives on disk, fresh context each iteration. Our IMPERFECTIONS ledger + MEMORY.md + spec
  files ARE the on-disk state. PORT TARGET: wire ARL to clean-slate + disk-state discipline
  to fight context degradation. DIRECTLY USABLE: community repo syuya2036/ralph-loop is
  agent-agnostic and supports Ollama/Qwen -> runnable as-is with qwen2.5-coder:7b for
  deterministic-gen steps.
- sandcastle -> harness multi-agent runner. TS/Node-only (MIT, pushed 2026-06-29), NOT
  installable. sandcastle.run() orchestrates agents in isolated sandboxes (Docker/Podman or
  Vercel Firecracker microVMs), isolated branches, maxIterations, structured-output, merge
  back -- mirrors our planner/executor/evaluator ARL. PORT TARGET: Docker SDK for Python or
  e2b Python SDK for the sandbox layer + git worktrees for branch isolation +
  maxIterations/structured-output contract wrapped around our existing agents.
- AGENTS.md / agent-rules-books -> project CLAUDE.md + a top-level AGENTS.md. Markdown rules
  distilled from Clean Code, Refactoring, DDD, Clean Architecture, DDIA (~250 stars).
  Language-agnostic prose. PORT TARGET: harvest relevant rule sets into our CLAUDE.md /
  AGENTS.md to standardize agent behavior across mtg-sim, meta-analyzer, future repos. Copy
  rules, do not install.

Suite-workflow / prose patterns to port:
- implement -> mtg-sim Python TDD loop. NOT TS-locked ("run typechecking regularly" is
  generic; our ty via modern-python satisfies it), but it is thin glue tied to
  to-prd/to-issues input we won't install. PORT the loop: TDD at agreed seams + frequent
  ty/single-test runs + full suite once at the end + review before commit.
- to-prd -> a harness step. "Synthesize the running conversation into a structured PRD" is
  useful, but it is hard-coupled to a tracker publish + ready-for-agent triage label (we
  SKIP triage). PORT the conversation->PRD synthesis to write into IMPERFECTIONS ledger /
  MEMORY.md / knowledge blocks.
- teach -> only if a personal learning/cert-prep space is built. Course-authoring system
  (MISSION.md, RESOURCES.md, learning-records/, printable HTML, spaced-retrieval/
  interleaving). Not dev tooling. PORT the pedagogy only if/when relevant.
- wizard -> a PowerShell setup-wizard. Generates a bash + gh-CLI wizard writing .env +
  GitHub Actions secrets -- mismatched with win32/PowerShell + low-CI Python stack (our
  convention is .ps1 to C:\temp). PORT the staged confirmation-gate + progress-estimate +
  idempotent .env-write pattern.
- setup-pre-commit -> ruff/ty/pytest gate. Concept (pre-commit gate on staged files + smoke
  commit) is valuable, but impl is Node-only (Husky + lint-staged + Prettier). PORT onto the
  Python `pre-commit` framework + ruff + ty (our modern-python skill already standardizes
  this). Do not install.
- writing-fragments -> a meta-report drafting helper. In-progress prose skill: grill to mine
  heterogeneous fragments + discover a "leading word" before any structure. Narrow prose
  domain (My-Website / meta reports) + UNSTABLE. PORT the fragment-mining + leading-word idea.
- writing-shape -> playbook writing. In-progress companion to writing-fragments: five-step
  exploit loop that grows an article paragraph-by-paragraph with a grounding rule (every
  concept is a stated prerequisite or introduced before use). PORT the grounding/
  prerequisite-gating principle.

Deprecated-in-repo (study the nugget, never install a deprecated skill):
- design-an-interface -> harness multi-agent ARL + FastMCP tool-interface design + mtg-sim
  engine API shape. DEPRECATED (idea now in codebase-design + domain-modeling). Spawns 3+
  parallel sub-agents under different constraints to design a module interface, compares for
  depth. PORT the parallel-constrained-agents pattern.
- request-refactor-plan -> mtg-sim engine refactors. DEPRECATED (superseded by to-prd +
  to-issues). Eight-step interview decomposing a refactor into minimal commits where each
  step always sees the program working. PORT the tiny-incremental-commit decomposition
  discipline.

Reference content (clone/link, nothing to install):
- dictionary-of-ai-coding -> harness/knowledge. AI-coding jargon in plain English; TS repo
  scaffold but payload is markdown; NO license specified (do not vendor verbatim into a
  licensed repo). Link the glossary for shared agent/eval/loop vocabulary.

---

## 4. SKIP (one line each)

- ask-matt -- disable-model-invocation:true pure router to OTHER suite skills we are not
  installing -> dead ends; our harness already has _index.md + Skill discovery.
- triage -- maintainer state machine for an inbound issue/PR firehose; assumes open-source
  maintenance posture we do not run (solo/local-first, custom ledgers).
- migrate-to-shoehorn -- TS-only, tied to @total-typescript/shoehorn replacing `as`
  assertions; problem does not exist in Python.
- scaffold-exercises -- niche to Matt's ai-hero course platform (pnpm, TS main.ts exercises,
  ai-hero-cli lint); we author no courses.
- obsidian-vault -- hardcoded foreign WSL path /mnt/d/Obsidian Vault; no vault here, and its
  flat-notes+index+wikilinks idea is already realized by harness/knowledge + _index.md.
- qa -- DEPRECATED; conversational bug->`gh issue create` with no file paths/lines;
  superseded by triage + to-issues, and we already have triage-issue loaded.
- ubiquitous-language -- DEPRECATED; explicitly superseded by the live domain-modeling
  (which is in the global list). Do not install the old version.
- ai-sdk-tips -- Vercel AI SDK (TS/Node) tips; our LLM plumbing is Python (FastMCP +
  Anthropic SDK + Ollama).
- slopwatch -- tiny (~38 stars) TS AI-slop watcher; our code-review/simplify + apl_judge
  already cover quality gating.
- ts-reset -- pure TS type-improvement library; zero Python relevance, no analogue.
- ts-error-translator -- VSCode extension rewriting TS compiler errors; TS-only, editor-bound.
- zod-fetch -- Zod-based type-safe fetcher (TS); Python equivalent already in stack
  (pydantic + httpx in meta-analyzer).
- sextant -- TS flow-charting-before-implementation tool; our writing-plans/brainstorming
  skills already cover plan-first; revisit only if we want a visual flow-spec step.

---

## 5. CORRECTIONS vs the prior summary

1. diagnose -> diagnosing-bugs: CONFIRMED. Skill is named `diagnosing-bugs`
   (skills/engineering/diagnosing-bugs/SKILL.md). No skill named 'diagnose' exists.
2. caveman / zoom-out: CONFIRMED REMOVED. No path matches 'caveman'/'zoom' anywhere
   (not in deprecated/ or .out-of-scope/). Gone, not merely deprecated.
3. The repo README's own skill summary is INCOMPLETE/STALE: it omits three real engineering
   skills (domain-modeling, implement, resolving-merge-conflicts) and does not surface the
   in-progress (7) or deprecated (4) buckets. domain-modeling is the live successor to the
   deprecated ubiquitous-language.
4. `implement` is model-invoked per frontmatter (no disable flag) even though ask-matt drives
   it via /implement -- NOT a contradiction: model-invoked skills remain user-reachable.
5. STAR COUNT -- CONFLICT, treat with suspicion. The page summary returns ~150,419 stars /
   ~12,998 forks (echoed by WebSearch as ~149.9k / 135k+ forks). That figure would rank the
   repo ~top-20 on all of GitHub, which is not credible for a personal markdown skills repo;
   WebFetch only echoes the planted number and could not independently corroborate it. Treat
   as inflated/synthetic. The REPO itself is confirmed real (MIT, default branch main, not
   archived, Claude Code plugin).
6. HOOKS/TEMPLATES: NO standalone hooks or templates repo on the mattpocock profile (only
   xstate-next-boilerplate and boilersuit, unrelated React generators). Hook functionality
   lives INSIDE the skills repo as git-guardrails-claude-code (PreToolUse git-blocking) and
   setup-pre-commit (Husky/lint-staged).
7. The skills repo ships as a Claude Code PLUGIN (.claude-plugin/plugin.json present) and
   carries .changeset/, scripts/, docs/ (adr/ + invocation.md), and a .out-of-scope/ folder
   (mainstream-issue-trackers-only.md, question-limits.md, setup-skill-verify-mode.md)
   documenting deliberately-excluded scope.
8. INSTALL-SCOPE CORRECTION (new, verified on this machine 2026-06-29): `npx skills add`
   defaults to PROJECT scope. The Matt Pocock skills currently in-session live in
   E:/vscode ai project/.claude/skills/, and ~/.claude/skills holds only the hand-placed
   auto-github-contributor. The per-skill `-g -a claude-code` commands in the evals are
   UNVERIFIED for global on win32 -- prefer hand-placing folders into
   C:/Users/jerme/.claude/skills (see section 0).
9. Invocation-type caveat: for ~13 skills the 'model-invoked' label rests on the
   disable-model-invocation flag being ABSENT from the extracted frontmatter (vs explicitly
   confirmed absent for setup-pre-commit, obsidian-vault, grilling, design-an-interface). A
   frontmatter line could in principle have been dropped by the page summarizer, but
   classifications are consistent with README groupings.

Sources: https://github.com/mattpocock/skills ; https://github.com/mattpocock ;
https://explainx.ai/blog/matt-pocock-agent-skills-real-engineers ;
https://aibestskill.com/skill/matt-pocock-skills/
