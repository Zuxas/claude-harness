# Repo Evaluation — Independent Verified Action Plan (2026-06-27)

Scope: 26 of 27 candidate repos/tools, independently re-researched. This plan foregrounds where my
direct research **diverged from the prior write-up**, and flags everything I **could not verify**.

The binding context for every decision: this workstation runs **live Gmail / Drive / Calendar /
Savecraft MCP credentials** inside Claude Code, and the FastMCP+Ollama ARL was just hardened against an
injection→RCE class of bug. That single fact moves several "obviously useful" tools from *install* to
*gate* or *skip*, because any tool that pours untrusted external text into a credentialed context, or
that runs its own shell/MCP server, inherits that blast radius.

---

## 1. TL;DR — Highest-Value Moves (whole project, not just sims)

1. **Adopt `blader/humanizer` for career writing (vet-then-install).** Pure markdown skill, zero code/
   network/tool access, directly serves the active SWE-transition resume/portfolio/LinkedIn need. Best
   risk-adjusted win on the board.
2. **Stand up a credential-isolated "dev/doc" Claude Code profile** with the Gmail/Drive/Calendar/
   Savecraft MCPs **disconnected**. This single piece of plumbing is the precondition that makes
   context7, Understand-Anything, and paper2code safe to use at all — build it before any of them.
3. **Pilot `upstash/context7` (gated, dev repos only)** for up-to-date docs on fast-moving libs
   (FastMCP, PyQt6, Pydantic, Ollama). Real daily coding value; safe only inside the isolated profile.
4. **Build the ARL hardening trio in-house — don't install the repos that inspired them:** SHA-256
   pre/post write-verify + rollback (idea from `mythos-router`), a skeptical false-positive validator +
   cross-session FP memory (from `mythos-research`), and a tiered "dangerous action" approval gate
   (from `hermes-webui`). ~100–250 LOC total, no new dependencies, complements the existing deny-list.
5. **Apply Meta's "Rule of Two" as a written design constraint** (from `awesome-prompt-injection`) on
   the two live risk surfaces: the ARL (untrusted input + code execution) and the Google MCPs
   (sensitive data + state change). It gives a crisp, citable gate for every future tool decision.

---

## 2. INSTALL NOW / VET-THEN-INSTALL (ordered)

There is **no INSTALL-NOW** tier — nothing cleared an unconditional install given the live MCP creds.

**VET-THEN-INSTALL (2):**

1. **`blader/humanizer`** — *career surface (resume/portfolio/cover letters/My-Website copy).*
   - Safe path: `git clone https://github.com/blader/humanizer`, **read `SKILL.md` once**, then copy
     the markdown to a pinned path under `~/.claude/skills` (prefer a pinned copy over a live clone that
     tracks `main`). Confirm it is the real `blader/humanizer` — typosquats exist (`Aboudjem/
     humanizer-skill`, `c-b-g-m/blader-humanizer`).
   - Security gating: none required — no code, no network, no tool access; cannot reach MCP creds.

2. **`PrathamLearnsToCode/paper2code`** — *mtg-sim surface (implement probability/ML papers, e.g.
   Karsten MTG-Math), plus a reusable codegen-prompt pattern.*
   - Safe path: `npx skills add PrathamLearnsToCode/paper2code/skills/paper2code`, but first **clone and
     read the bundled Python scripts**, **pin the commit** (repo is 5 commits, all 2026-04-03 — popular
     but barely maintained). It runs author scripts + `pip install pymupdf4llm pdfplumber requests
     pyyaml` on invocation.
   - Security gating: **mandatory** — invoke only inside the credential-isolated profile (Gmail/Drive/
     Calendar/Savecraft MCPs OFF), ideally a throwaway venv. It ingests untrusted arXiv PDF text, the
     exact injection-into-creds vector to keep away from live tools.

---

## 3. STUDY-ONLY (mine for patterns; do not run in the credentialed env)

Architecture / security references (highest leverage first):

- **`thewaltero/mythos-router`** — Strict-Write-Discipline: pre/post SHA-256 snapshot + hash-chained
  receipts + rollback. **Reimplement in-house** (~100–150 LOC Python) so a hallucinated/injected "I
  wrote file X" is caught against actual disk state. *Do not install — ships a crypto token (see §5/§6).*
- **`Keyvanhardani/mythos-research`** — sink-guided slicing, **adversarial self-challenge**, a separate
  **skeptical false-positive validator pass**, and **cross-session FP memory writeback**. Clean Apache-2
  Bash, non-exfiltrating; port the *methodology* into the ARL's generated-code review loop.
- **`nesquena/hermes-webui`** — its **tiered approval card** for dangerous shell commands (allow once /
  this session / always / deny). Port the UX as the human-in-the-loop gate in front of ARL code exec.
- **`Joe-B-Security/awesome-prompt-injection`** — index of MCP/indirect-injection literature; pull the
  **Rule of Two** framing and the **Garak** scanner as a candidate to evaluate against the ARL deny-list.
- **`artvandelay/codex-agentic-patterns`** — read the **Sandbox Escalation** and **approval-gate** write-
  ups to sanity-check ARL autonomy boundaries. Read on GitHub; do not run the OpenAI-keyed examples here.
- **`NousResearch/hermes-agent`** — borrow its **SQLite FTS5 cross-session memory** design and self-
  improving skill-loop structure for the ARL's memory layer. (Install path is pipe-to-shell only — §5.)
- **`kyegomez/swarms`** — read the orchestration topologies (sequential / concurrent / hierarchical /
  graph) as patterns to enrich the in-house ARL loop. Do not pip-install (§5/§6).
- **`Neonia-io/agent-mcp-examples`** — study the MCP-tool-as-native-tool wrappers (LangGraph, Rust Rig,
  Vercel AI SDK) and the **"local JQ filter instead of loading a 5MB blob into context"** idea —
  reimplement locally for big Untapped/MTG JSON. Do not adopt the proprietary cloud gateway.
- **`mnfst/awesome-free-llm-apis`** — shopping list for a manual cloud-burst fallback (Groq/Cerebras/
  OpenRouter) when the 3080 saturates or Claude 429s — **only for non-sensitive synthetic MTG content**,
  behind a data-classification gate. It's reference data, not a router you install.
- **`microsoft/BitNet`** — read the ternary-weight CPU-kernel approach for awareness. No coder-tier
  b1.58 model exists, so it cannot replace qwen2.5-coder:7b; re-evaluate only if such a model ships.
- **`kyegomez/OpenMythos`** — read-only learning reference for recurrent-depth/looped-transformer
  concepts (SWE study). Don't install into any ARL/MCP venv; 770M+ MoE is impractical on a 3080 anyway.
- **`sindresorhus/awesome`** — human discovery index (awesome-mcp-servers / awesome-claude / awesome-
  llm). Browse out-of-loop; vet every candidate it surfaces independently. Never wire into the ARL.
- **`giuliacassara/awesome-social-engineering`** — thin but topical: phishing/pretext taxonomy for the
  human-factors section of an MCP-injection threat model. Reading only.

---

## 4. PILOT-WITH-GATE (trial with an explicit kill-criterion)

1. **`upstash/context7`** — *dev coding docs across repos.*
   - Gate: enable **only** in per-project `.claude` MCP config for code repos; keep Google/Savecraft
     MCPs **out of those same project configs**; prefer the remote read-only endpoint; treat all
     returned docs as untrusted **data, never instructions**; skip the API key initially.
   - **Kill-criterion:** if doc text and sensitive tools cannot be guaranteed isolated in your config
     model (skill descriptions leak globally into every session), or if any returned doc is observed
     attempting to direct tool use → drop it. Never feed the ARL.

2. **`Egonex-AI/Understand-Anything`** — *onboarding/architecture maps of the multi-repo codebase;
   diagrams double as portfolio artifacts.*
   - Gate: install by **manual `git clone` pinned to a reviewed commit** — never `curl|bash` / `iwr|iex`;
     **read the skill `.md` files before enabling**; enable **only** in a dedicated sandbox project with
     sensitive MCPs disconnected; **never pass `--auto-update`**; point it at local Ollama
     (qwen2.5-coder:7b) so code never leaves the box.
   - **Kill-criterion:** if plugin enablement cannot be scoped away from credentialed sessions →
     downgrade to study-only. Skip on any profile with the live MCP stack attached.

---

## 5. SKIP (one-line reasons; security risks called out)

- **`elder-plinius/OBLITERATUS`** — **SECURITY/CATEGORY RISK.** Safety-alignment-removal toolkit by a
  jailbreak persona; README is manipulative content; hosted telemetry on by default. Off-topic + hostile.
- **`PurpleAILAB/Decepticon`** — **SECURITY RISK.** Autonomous offensive agent; `curl|bash` install +
  Docker-socket/root reach next to live OAuth creds. Out of scope.
- **`itwizardo/hackcode`** — **SECURITY RISK.** `curl|bash` from a mutable `dev` branch + silent
  auto-sync every 6h + shell-capable bundled MCP + fabricated "Anthropic leak" marketing. Disqualifying.
- **`thewaltero/mythos-router`** — **SUPPLY-CHAIN RISK.** Single maintainer + `$MYTHOS` crypto token +
  MCP file read/write/exec next to live creds. Borrow the SWD idea (§3), never the package.
- **`Manavarya09/design-extract` (npm `designlang`)** — **UN-AUDITABLE + low relevance.** GitHub repo
  AND owner account 404; npm manifest stripped of repository URL; postinstall runs `playwright install`.
  Need already covered by in-house `ui-ux-pro-max`.
- **`juliusbrussee/caveman`** — `curl|bash`/`iex` install + MCP middleware near creds, and it only trims
  *output* tokens by degrading precision — counterproductive for code/sim/resume. RTK covers this safer.
- **`nikopueringer/CorridorKey`** — film green-screen VFX; zero overlap with any project surface.
- **`v2-dev/awesome-artificial-intelligence`** — dead 1-star fork; use canonical `owainlewis/...` if any.
- **`speedguide-tcp-optimizer`** — closed-source Windows registry tweaker; not a repo; no relevance.
- **`namebench`** — abandoned DNS benchmark (frozen Google Code Archive); no integration value.

---

## 6. DIVERGENCES FROM THE PRIOR WRITE-UP (corrections + unverifiable)

**Corrections / contradictions from my direct research:**

- **context7:** prior dispositioned **install-now** → I downgraded to **pilot-with-gate**. Facts (58k
  stars, MIT, active, doc-injection MCP) are accurate, but it injects untrusted community-contributed
  doc text into contexts that elsewhere hold live creds; Upstash disclaims doc accuracy/security.
- **swarms:** prior said **"last release 6.8.1, Dec 2024"** — **WRONG/stale**; PyPI shows **v13.0.0
  (2026-06-12)**, heavily maintained. **NEW (prior missed):** entangled with a `$swarms` crypto token;
  maintainer faced public plagiarism/scam accusations. Risk is **high**, not benign.
- **hermes-agent:** prior labeled it **"MCP"** — **it is NOT an MCP server** (standalone agentskills.io
  runtime). Prior said **"star count likely inflated"** — API reports **204k stars**, internally
  consistent; "inflated" is **unproven**, not confirmed. Install is **pipe-to-shell only** (understated).
- **hermes-webui:** prior said **"mobile clients"** — it's a **mobile-responsive web UI**, not native
  apps; prior **undersold** the underlying full shell-executing, self-skill-writing autonomous agent.
- **Understand-Anything:** prior implied **Claude-Code-only** — it's **multi-platform**, and Claude Code
  uses the **plugin marketplace, not `curl|bash`**. It is **not an MCP server** (loads skills into your
  agent). I **scanned `install.sh` — clean** (git clone/pull + symlinks; no eval/base64/hooks). The
  README's **`--auto-update` post-commit hook could NOT be confirmed** in the script. Star velocity (68k
  in ~3 months) is a marketing yellow flag.
- **awesome-prompt-injection:** prior claimed it contains a **"security checklist"** — **WRONG**; it is
  purely outbound links, no actionable checklist of its own.
- **awesome-free-llm-apis:** prior framing OK on substance but **mislabels the artifact** — it's static
  CC0 reference data, not a tool/fallback-router you install.
- **design-extract:** prior said **"COULD NOT verify — confirm it exists."** It exists on npm, but the
  **canonical GitHub repo AND owner account now 404** (confirmed 3 ways), and the **npm manifest has its
  repository/homepage fields stripped** — so the shipping tarball maps to **no auditable source**.
- **agent-mcp-examples:** prior said **"COULD NOT VERIFY."** It **exists** (created 2026-04-22) — but it
  is **first-party demo code for the proprietary Neonia cloud gateway**, not a generic MCP example set;
  every example routes data through Neonia's remote servers.
- **mythos-research:** prior said **"Mythos/Glasswing fiction framing."** **INCORRECT** — there is **no
  fiction**; it presents "Anthropic Mythos Preview / Project Glasswing" as real (claimed) product
  codenames. Prior reviewer mistook unfamiliar codenames for invented lore. "Real CVE work" is
  **plausible but UNVERIFIED**.
- **mythos-router:** prior **missed the deciding factor** — a `$MYTHOS` crypto token tied to the package.
  This makes it **high risk**, not "harmless fiction marketing."
- **OBLITERATUS:** prior said it **requires A100-class VRAM** — **WRONG**; it scales CPU/1GB → multi-GPU
  and **could run on the 3080**. Conclusion (skip) unchanged; hosted telemetry defaults **ON**.
- **BitNet:** prior framing OK; I **sharpened** the decisive point — the thin model ecosystem (no
  coder-tier b1.58 model) makes "free the GPU" a **bad trade** here, not a footnote.
- **codex-agentic-patterns:** prior's **"best architectural reference for the ARL"** is an **unverified
  superlative** — it's a small (~39-star), young, single-maintainer repo derived from **OpenAI Codex**,
  not a Claude/FastMCP/Ollama stack. Useful, not "the best."
- **paper2code:** stars **~1.4k** (prior said ~1.3k); **only 5 commits, all one day** — barely maintained.
- **Decepticon:** "per-objective context isolation" is more accurately **network/process isolation**
  (sandbox-net vs management-net), not LLM context-window isolation.
- **humanizer:** install is **`git clone` / `npx skills add`**, **not `curl|bash`**.
- **caveman:** the 65% saving is **output/generation tokens only** (thinking/input untouched); it's a
  **style prompt**, not a compression codec.
- **OpenMythos:** it is a **pip-published package** (not just reading material); perf claims unverified
  hype; ~14k stars likely inflated for the author's pattern.

**Could NOT verify / low confidence (fetch failed or summarizer-mediated):**

- **hermes-webui** — retrieved via WebFetch's **summarizing model**; the ~15k star count, exact version,
  and a claimed NousResearch `curl|bash` path are **possibly confabulated** and are **not load-bearing**.
  (confidence: medium)
- **design-extract** — verified from the **npm registry manifest + web search only**; the **GitHub
  source was unreachable (404)**, so the shipping code is **un-auditable**. (404 finding: high; tool
  trust: cannot be established)
- **speedguide-tcp-optimizer** — `speedguide.net` WebFetch returned **HTTP 403 (bot-blocked)**; verified
  via WebSearch across mirrors. (confidence: high on facts, no direct page read)
- **namebench** — WebFetch returned only the **client-rendered SPA shell**; verified via WebSearch +
  Wikipedia. (confidence: high)
- **mythos-research** — coordinated-disclosure **CVE/GHSA claims are unverified** (author enumerated none).
- **Understand-Anything** — the **`--auto-update` post-commit hook** behavior could not be confirmed.
- **awesome-prompt-injection / awesome-free-llm-apis** — specific 2026-dated stats (Morris II worm, Snyk
  "36% of agent skills" malware, provider rate limits) are forward-referenced and **unconfirmed**.

---

## 7. RECOMMENDED SEQUENCE — Next 3 Steps

1. **Build the isolation boundary first.** Create a dedicated "dev/doc" Claude Code project profile with
   the Gmail/Drive/Calendar/Savecraft MCPs disconnected. Confirm your config model can scope plugin/MCP
   enablement per-project (this is the kill-criterion gate for steps 2–3). Nothing else proceeds without it.
2. **Land the two safe wins.** Vet-then-install **`blader/humanizer`** (read SKILL.md, pin a copy) for
   career writing — needs no isolation. Then, inside the isolated profile, **pilot `context7`** on one
   code repo and **vet-then-install `paper2code`** (read scripts, pin commit, throwaway venv).
3. **Harden the ARL in-house from the study-only patterns.** Implement the SHA-256 write-verify+rollback
   (mythos-router), the skeptical FP-validator + cross-session FP memory (mythos-research), and the
   tiered approval gate (hermes-webui); write the **Rule of Two** constraint into the ARL + MCP design
   docs. No new dependencies — all three borrow ideas, not code.

---

*Counts:* install-now **0** · vet-then-install **2** · study-only **13** · pilot-with-gate **2** ·
skip **9** (total 26).
