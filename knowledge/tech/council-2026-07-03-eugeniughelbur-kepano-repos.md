---
name: council-2026-07-03-eugeniughelbur-kepano-repos
description: Council verdict on adopting 5 GitHub repos (eugeniughelbur x4 + kepano/obsidian-skills) into the Zuxas harness
metadata:
  type: reference
---

## COUNCIL VERDICT: which of 5 MIT repos to adopt into the harness

**Date:** 2026-07-03 | **Seats:** 4 (Analyst, Contrarian, Empiricist + cross-vendor Codex/gpt-5.5) | **Blind protocol:** confirmed y | **Vendors:** Anthropic x3 + OpenAI x1

### Per-repo verdict (confidence)
1. **obsidian-second-brain** — **AGAINST, decisive** (high). Auto-rewrites 5-15 vault pages per URL ingest; that is uncontrolled mutation of a knowledge source the user hand-curates with a changelog/WRITING-BACK discipline. Its README rollback safety net assumes git; this workspace is NOT a git repo, so the net is absent. Structurally duplicates harness/knowledge/ + MEMORY.md ("two sources of truth"). Steal ideas (challenge/synthesis prompt patterns) reimplemented read-only; do not install.
2. **kepano/obsidian-skills** — **FOR, selective** (high). Authoritative (Steph Ango, Obsidian CEO), 39.6k stars CONFIRMED live, near-zero bus-factor. Adopt **defuddle** (web->clean-markdown, token-saving ingest utility, vault-independent). The user DOES run Obsidian as a viewer over harness/knowledge/ (HARNESS_STATUS.md:105), so **obsidian-markdown** and **json-canvas** are also plausibly useful for authoring/visual maps; **obsidian-bases** and **obsidian-cli** are lower value. Install the skills, use what fits.
3. **agents-md** — **AGAINST** (medium). Solves a cross-tool problem the user (Claude-Code-first) doesn't have. Symlinking CLAUDE.md is risky against a hand-authored MANDATORY-STARTUP CLAUDE.md; Windows symlinks need admin/Dev-Mode. 3 stars, single author. Skip.
4. **gpt-image-cookbook** — **AGAINST** (medium). Category error vs the actual need (report GUI/layout polish != raster image gen). Imagen/Flux are STUBS (Empiricist), only gpt-image-2 works; needs paid keys. Marginal at best for My-Website hero art. Skip.
5. **doceo** — **FOR, low-stakes / orthogonal** (Analyst) vs **AGAINST, duplication** (Contrarian/Codex). No API keys, no deps, memory local. Zero conflict surface with the harness because it's a personal tutor, not a knowledge-writer. Verdict: harmless opt-in if a learning tool is wanted; ignore otherwise. Not a priority.

### Where the council agreed / clashed
- **Unanimous:** reject obsidian-second-brain (all 4 seats, same reason: it auto-mutates a working knowledge base). Reject agents-md + gpt-image-cookbook.
- **Clash — kepano scope:** Codex said "FOR, all 5 skills useful"; Analyst/Contrarian said "defuddle ONLY, the rest presuppose an Obsidian vault the user doesn't run." **Chairman resolution:** the user DOES run Obsidian over harness/knowledge/ (HARNESS_STATUS.md:105 "Obsidian renders the blocks as a visual graph") — so the vault-dependent skills are more relevant than A/C assumed, but still niche. Land on FOR-selective, defuddle first.
- **Clash — doceo:** orthogonal-harmless vs duplicate-memory-layer. Low stakes either way.

### Blind spots flagged (TODOs)
- Confirm **defuddle** runs standalone without a full Obsidian vault before install (Analyst caveat, unverified).
- obsidian-second-brain version string (v0.11.1) and "44 commands" are README-level only, never primary-audited (Empiricist).

### Dissent worth preserving
- Codex's broader "adopt the whole kepano bundle" may age well IF the user leans harder into Obsidian-native authoring (Bases/Canvas). Revisit if the knowledge base grows a visual-map layer.

### EVIDENCE INDEX
- github.com/eugeniughelbur/obsidian-second-brain (README: "One URL in. The vault rewrites itself"; rewrites 5-15 pages) — stars 2937 CONFIRMED via api.github.com, pushed_at 2026-07-03, MIT.
- github.com/kepano/obsidian-skills — stars 39604 CONFIRMED via api.github.com, MIT, owner kepano = Steph Ango.
- github.com/eugeniughelbur/{agents-md 3*, gpt-image-cookbook 3* (Imagen/Flux stubs), doceo 2*} — all MIT, all CONFIRMED, single-author (6 repos, 88 followers) = bus-factor concern.
- E:\vscode ai project\harness\HARNESS_STATUS.md:105 — "Obsidian renders the blocks as a visual graph for human editing."
- Env: workspace is NOT a git repo (removes second-brain's rollback path).

### CHANGELOG
- 2026-07-03: created. Council verdict on 5-repo adoption question.
