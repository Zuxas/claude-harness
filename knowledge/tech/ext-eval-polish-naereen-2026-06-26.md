---
title: "External Eval — Quick-Win Polish + Naereen/* Fold-Ins"
domain: tech
type: external-evaluation
created: 2026-06-26
author: research subagent (Opus 4.8)
status: draft-for-review
scope: read-only research + spec; no source code modified
sources_verified: 2026-06-26 via WebFetch (GitHub) + local file reads
related:
  - E:/vscode ai project/thingstolookinto.md   # prior audit (2026-06-21) — verified below
  - E:/vscode ai project/My-Website/            # TeamResolve site (local)
public_repos:
  - Zuxas/mtg-sim            # Python, MIT (confirmed on GitHub)
  - Zuxas/mtg-meta-analyzer  # Python, MIT (confirmed on GitHub)
  - Zuxas/claude-harness     # Python, NO license shown (must add LICENSE)
  - Zuxas/TeamResolve        # HTML,  NO license shown (must add LICENSE)
  - Zuxas/Zuxas              # profile README — already exists (updated 2026-06-12)
---

# Quick-Win Polish + Which Naereen/* Repos to Fold In

Topic owner asked specifically about https://github.com/Naereen (Lilian Besson —
French CS professor, ex-CentraleSupelec/Inria PhD, MTG L1 judge, 628 followers).
His repos are small-star but clean, permissive-where-it-counts, and several are
literally MTG tooling. This doc verifies each license, then gives sized,
paste-ready quick wins.

## 0. License confirmation (fetched 2026-06-26, not trusted from prior audit)

| Repo | License (verified) | Reuse verdict |
|------|--------------------|---------------|
| Naereen/badges | **MIT** | Fine. It is a *reference list* of shields.io/forthebadge markdown. Badges themselves need no license; credit Naereen as the inspiration in a README comment. |
| Naereen/me | **CC-BY 3.0** (Stellar by HTML5up @ajlkn, also CC-BY 3.0) | Fold-in OK *with attribution*. Must keep a visible credit ("Design: Stellar by HTML5up") and CC-BY notice. |
| Naereen/StrapDown.js | **MIT** | Fold-in OK. Keep LICENSE + (c) Lilian Besson 2015-16 header. |
| Naereen/LaTeX_template_to_print_Magic_cards | **MIT** | Fold-in OK. Keep (c) notice. |
| Naereen/My-Android-app-to-track-life-points | **MIT** (worded "MIT Licensed for personal use" — mild caveat; SvelteKit/TS/Tailwind PWA, updated 2026-02) | Fold-in OK but the "personal use" wording is non-standard — open an issue / email to confirm before any *commercial* Twitch monetization. Ideas/clean-reimplement is always safe. |
| Naereen/generate-word-cloud.py | **GPL-3.0** | COPYLEFT TRAP — do NOT link/import. Use the underlying lib `wordcloud` (by @amueller, MIT) directly. Prior audit was correct. |
| Naereen/ansicolortags.py | **MIT** (PyPI: `ansicolortags`) | Fine, but `rich`/`colorama` already cover this — skip unless you want zero-dep. |

Prior-audit corrections: thingstolookinto.md listed Naereen/me, Naereen/My-Android
under "non-standard license (read LICENSE)". Confirmed now: me = CC-BY 3.0,
Android = MIT (with a "personal use" phrasing quirk). badges/StrapDown/LaTeX/ansicolor
all MIT as listed.

## 1. README badge blocks (paste-ready)

Brand hex pulled from `My-Website/styles.css :root`: teal `--accent #65bcd5`,
gold `--gold #d4a84b`, dark `--bg-dark #2e2f3d`. Custom badges use these.
Dynamic badges (last-commit, repo-size, license, website) auto-update — prefer them
over hardcoded numbers. Metrics grounded: meta-analyzer 91% / 147 archetypes / 262k
matches (profile README + NEXT_STEPS.md:909), sim ~121k LOC / 1k-30k iters / 420 .py
files, TeamResolve 94 playbook files (`find ... *playbook*.html` = 94).

### Zuxas/mtg-meta-analyzer  (MIT confirmed — dynamic license badge works)
```markdown
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/github/license/Zuxas/mtg-meta-analyzer)](https://github.com/Zuxas/mtg-meta-analyzer/blob/main/LICENSE)
[![Last commit](https://img.shields.io/github/last-commit/Zuxas/mtg-meta-analyzer)](https://github.com/Zuxas/mtg-meta-analyzer/commits/main)
[![Repo size](https://img.shields.io/github/repo-size/Zuxas/mtg-meta-analyzer)](https://github.com/Zuxas/mtg-meta-analyzer)
[![Classifier accuracy](https://img.shields.io/badge/classifier_accuracy-91%25-65bcd5)](https://github.com/Zuxas/mtg-meta-analyzer)
[![Matches](https://img.shields.io/badge/matches-262k+-d4a84b)](https://github.com/Zuxas/mtg-meta-analyzer)
[![Archetypes](https://img.shields.io/badge/archetypes-147-65bcd5)](https://github.com/Zuxas/mtg-meta-analyzer)
[![scikit-learn](https://img.shields.io/badge/scikit--learn-F7931E?logo=scikit-learn&logoColor=white)](https://scikit-learn.org/)
[![PyQt6](https://img.shields.io/badge/PyQt6-41CD52?logo=qt&logoColor=white)](https://pypi.org/project/PyQt6/)
```

### Zuxas/mtg-sim  (MIT confirmed)
```markdown
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/github/license/Zuxas/mtg-sim)](https://github.com/Zuxas/mtg-sim/blob/main/LICENSE)
[![Last commit](https://img.shields.io/github/last-commit/Zuxas/mtg-sim)](https://github.com/Zuxas/mtg-sim/commits/main)
[![Code size](https://img.shields.io/github/languages/code-size/Zuxas/mtg-sim)](https://github.com/Zuxas/mtg-sim)
[![Engine](https://img.shields.io/badge/engine-Monte_Carlo-65bcd5)](https://github.com/Zuxas/mtg-sim)
[![Sim scale](https://img.shields.io/badge/sim_scale-1k--30k_iters%2Fmatchup-d4a84b)](https://github.com/Zuxas/mtg-sim)
[![Win model](https://img.shields.io/badge/win--prob-gradient_boosting-65bcd5)](https://github.com/Zuxas/mtg-sim)
```

### Zuxas/claude-harness  (NO LICENSE on GitHub — add one FIRST)
> Add a real `LICENSE` (MIT) before pushing badges, or the dynamic license badge
> 404s. The static MIT badge below is safe meanwhile.
```markdown
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://github.com/Zuxas/claude-harness/blob/main/LICENSE)
[![Last commit](https://img.shields.io/github/last-commit/Zuxas/claude-harness)](https://github.com/Zuxas/claude-harness/commits/main)
[![Claude Code](https://img.shields.io/badge/Claude_Code-agentic-d4a84b)](https://docs.anthropic.com/en/docs/claude-code)
[![Local LLM](https://img.shields.io/badge/local_LLM-Gemma_12B-65bcd5)](https://github.com/Zuxas/claude-harness)
[![Pattern](https://img.shields.io/badge/pattern-three--agent-65bcd5)](https://github.com/Zuxas/claude-harness)
```

### Zuxas/TeamResolve  (NO LICENSE on GitHub — add CC-BY or MIT first)
```markdown
[![Live site](https://img.shields.io/website?url=https%3A%2F%2Fzuxas.github.io%2FTeamResolve%2F&label=live%20site)](https://zuxas.github.io/TeamResolve/)
[![Deployed: GitHub Pages](https://img.shields.io/badge/deployed-GitHub_Pages-222?logo=github)](https://zuxas.github.io/TeamResolve/)
[![Playbooks](https://img.shields.io/badge/playbooks-94-d4a84b)](https://zuxas.github.io/TeamResolve/)
[![Formats](https://img.shields.io/badge/formats-Modern_·_Standard_·_Pioneer-65bcd5)](https://zuxas.github.io/TeamResolve/)
[![Last commit](https://img.shields.io/github/last-commit/Zuxas/TeamResolve)](https://github.com/Zuxas/TeamResolve/commits/main)
```

Badge work sizing: **Value 4 / Effort S / Risk none.** Touches each repo's
`README.md` top block only. Credit line to add once (any repo): `<!-- badge set
inspired by Naereen/badges (MIT) -->`. Add LICENSE files to claude-harness +
TeamResolve as a prerequisite (Effort S).

## 2. Highest-value real fold-ins (pick: StrapDown.js #1, life-tracker #2)

### #1 — StrapDown.js -> zero-build Team Resolve guide pages   [Value 4 / Effort S / Risk Low]
MIT, single ~32KB client-side script (jsdelivr CDN), renders raw Markdown to a
styled page in-browser. We already emit `My-Website/ALL_GUIDES_EXPORT.md` and
per-deck intake markdown — StrapDown turns those into hosted pages with **zero
build step**, complementing (not replacing) the rich HTML playbook pipeline. Best
fit: fast internal/scratch matchup notes that don't justify the full playbook CSS.
Caveat: StrapDown is stale (last release 2016, bundles an old marked.js) — pin a
known-good CDN version and don't feed it untrusted markdown (XSS surface).
Integration steps:
1. Add `My-Website/notes/strapdown.min.js` (vendored, keep MIT header + (c) line) OR
   reference `https://cdn.jsdelivr.net/gh/Naereen/StrapDown.js@master/strapdown.min.js`.
2. Create `My-Website/notes/guide.html` wrapper: `<xmp theme="..." style="display:none;">`
   pattern from StrapDown's example1.html; load the `.md` via the wrapper.
3. Inject brand: override StrapDown's CSS vars with teal `#65bcd5` / gold `#d4a84b`
   / dark `#2e2f3d` so notes match the site.
4. Link from `deck-guides.html` under a new "Quick Notes" section.
Touches: `My-Website/notes/` (new), `My-Website/deck-guides.html` (one link).
Credit: footer "Markdown rendering: StrapDown.js by Lilian Besson (MIT)".

### #2 — Life-tracker -> OBS browser-source overlay   [Value 3 / Effort M / Risk Med]
MIT (note "personal use" phrasing — confirm before monetized streams). It is a
SvelteKit/TS/Tailwind PWA, already a hosted web page, so an OBS "Browser Source"
can point at a styled build. Value is Twitch/stream production for Team Resolve.
Integration steps (do as a clean reimplement to dodge the license caveat + avoid
pulling a full SvelteKit toolchain into this repo):
1. Build a standalone single-file `liferesolve.html` (vanilla JS) — dual-player
   life totals, +/- tap zones, large readable font, transparent background for OBS.
2. Brand teal/gold/dark; add Team Resolve wordmark corner.
3. Host on GitHub Pages (or local file) and add as OBS Browser Source (e.g.
   1920x300, CSS `body{background:transparent}`).
4. Keep a credit comment: "Inspired by Naereen/My-Android-app...life-points (MIT)".
Touches: new standalone file only; nothing in existing app code.
Why reimplement vs fork: avoids the "personal use" wording risk and a Svelte build
in our otherwise-static site; the feature is ~150 lines of vanilla JS.

### Bonus low-effort — LaTeX Magic-card template   [Value 2 / Effort S / Risk Low]
MIT, 63x88mm proxy sheets via pdflatex. Genuinely useful for RC brew testing
(proxy before buying paper). Adapt `template.tex` with navy/gold borders; keep
(c) notice. Standalone tool; touches nothing in the app. Skip generate-word-cloud
entirely (GPL) — if you want keyword clouds, call `wordcloud` (MIT) directly.

## 3. Zuxas profile / landing-page plan (from Naereen/me)

Status check: **a profile README already exists** at Zuxas/Zuxas (updated
2026-06-12) — strong copy already (Navy background, 4 projects, 91%/147 archetypes,
~121k-line sim, LinkedIn link). So the gap is NOT the README; it is a richer
**github.io landing page** that a recruiter can browse.

Plan — scaffold `zuxas.github.io` (user Pages site) using HTML5up **Stellar**
(the actual template behind Naereen/me; CC-BY 3.0):
1. Download Stellar fresh from html5up.net (clean attribution) rather than copying
   Naereen/me's customizations — both are CC-BY 3.0; keep the "Design: HTML5up
   Stellar (@ajlkn), CC-BY 3.0" credit in the footer.
2. Reuse the existing profile-README copy as section text. Three project cards:
   mtg-meta-analyzer (91% / 147 archetypes / 262k matches), mtg-sim (Monte Carlo,
   ~121k LOC, win-prob model), claude-harness (local Gemma 12B, three-agent).
3. Brand to bridge MTG + AI/ML hiring: teal `#65bcd5`, gold `#d4a84b`, dark
   `#2e2f3d` (matches Team Resolve so the portfolio feels unified).
4. Sections: hero (one-line pitch + LinkedIn/GitHub), Projects, "Live demo ->
   Team Resolve", Skills (Python/SQLite/PyQt6/scikit-learn/MCP), Contact.
5. Cross-link: profile README -> landing page -> Team Resolve -> repos (with the
   new badges). One coherent funnel for job applications.
Value 3 / Effort M / Risk Low. Touches: new `zuxas.github.io` repo only.

## Changelog
- 2026-06-26: Created. Verified 7 Naereen repos + 5 Zuxas repos live; confirmed
  licenses; authored paste-ready badge blocks; picked StrapDown.js + life-tracker
  as fold-ins; profile landing-page plan. Advisor call was rate-limited (noted).
