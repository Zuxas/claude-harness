---
title: "GUI Basic/Pro toggle — progressive disclosure for first-timers + endgame depth"
status: "IMPLEMENTED-PENDING-VISUAL-CHECK"
created: "2026-07-01"
updated: "2026-07-01"
project: "mtg-meta-analyzer"
estimated_time: "S-M (~1 focused session for items 1-2; +S each for 3-5)"
related_findings:
  - "E:\\vscode ai project\\GUI-UX-ASSESSMENT-2026-07-01.md"
related_commits: []
supersedes: null
superseded_by: null
---

# Spec: Basic/Pro progressive disclosure

> **Implementation note (2026-07-01):** Built the Basic|Pro title-bar segmented
> control (existing users w/ decks or match history default Pro, fresh installs
> Basic), dynamic add/remove of LADDER / SIMULATE / PREDICTIONS / CALIBRATION /
> HYPOTHESES via the Ask-Claude tab pattern, META sub-tab reorder (advanced
> last), subtitles, dismissible Dashboard banner, Ctrl+K hint + Help menu, and
> empty-state coaching. 388 tests green. Visual check on a running GUI pending.

## Goal
Make the GUI approachable on day one without removing any endgame depth: default a
newcomer to the everyday surfaces, let power tabs be opt-in via one title-bar toggle.
Serves both audiences from the same build (the stated product requirement).

## Scope
IN: (1) a Basic/Pro level toggle that shows/hides advanced tabs; (2) one-line subtitles
disambiguating the three winrate matrices + event surfaces; (3) a dismissible Dashboard
"first 3 things to try" banner; (4) an on-screen Ctrl+K hint + Help menu entry; (5)
empty-state coaching on Pro tabs with no data.
OUT: any change to analysis engines, data, or the tabs' internal behavior; visual
re-theming; the PWA/phone surface (separate track).

## Pre-flight reads (MANDATORY)
1. GUI-UX-ASSESSMENT-2026-07-01.md (the findings this implements)
2. gui/main_window.py:360-405 — the EXACT pattern to reuse: nested QTabWidgets +
   dynamic `_add_claude_tab()` / `_on_api_key_changed` add-remove of tabs by signal.
3. gui/state.py:69-85 (UIState.get/set dotted paths) + gui/state_keys.py (add a
   `UI_LEVEL = "global.ui_level"` constant here).
4. gui/widgets/command_palette.py (the Ctrl+K surface item 4 exposes).

## Steps
1. **Level state.** Add `state_keys.UI_LEVEL = "global.ui_level"` (values "basic"|"pro",
   default "basic"). Read on startup via UIState.get; persist on toggle. New users get
   Basic; existing users are unaffected only if we default to "pro" for a DB with
   >0 saved decks — DECISION for the user (see Open questions).
2. **Toggle control.** A segmented Basic|Pro control in the title-bar/toolbar row (near
   the existing refresh button, main_window.py:285). On change: call a new
   `_apply_ui_level(level)` that adds/removes the Pro sub-tabs using the SAME
   add/removeTab mechanism `_add_claude_tab`/`_on_api_key_changed` already use — do NOT
   invent a second mechanism.
3. **Classify tabs.** Pro-only (hidden in Basic): META→{Predictions, Calibration, Ladder,
   Simulate}, TOURNAMENT→Hypotheses. Basic-always: Dashboard, META→Charts, META→Matchup
   Data, Decks (both), Search, Tournament→{Event Optimizer, Match Log}, Resources,
   Puzzles, Settings. (Rationale + citations in the UX assessment.) On removeTab, keep the
   widget object alive for re-add (mirror the AI-tab pattern — they aren't destroyed).
4. **Guardrail:** if the persisted LAST_ACTIVE_TAB_PATH points at a now-hidden Pro tab
   when level=basic, fall back to Dashboard (don't restore into a hidden tab).
5. **Subtitles (item 2).** Add a one-line QLabel under each ambiguous tab's header:
   Matchup Data="Real tournament results"; Calibration="How close the sim is to reality
   (advanced)"; Ladder="MTGA online-ladder meta"; Event Optimizer="Build an expected
   field, get your equity"; Event Hub="Find & bookmark real events". Text only.
6. **Dashboard banner (item 3).** Dismissible (persist `global.dash_banner_dismissed`),
   3 links: Decks→Analyze, Search, the meta table. Show only when not dismissed.
7. **Ctrl+K hint (item 4).** Small "Press Ctrl+K to jump anywhere" affordance in the
   toolbar corner + a Help menu entry that opens the palette. XS.
8. **Empty-state coaching (item 5).** On each Pro tab, when its data source is absent
   (no MTG_SIM_PATH for Calibration, no logged predictions, etc.), render a one-sentence
   "what this is / how to enable" placeholder instead of a blank/error grid.

## Validation gates (falsifiable)
- G1 default-Basic: fresh DB launches in Basic; only the Basic tab set is present.
- G2 toggle round-trip: Basic→Pro reveals exactly the 5 Pro tabs; Pro→Basic removes
  exactly them; no duplicates after 10 toggles (widget reuse, not re-instantiation).
- G3 persistence: level survives restart; hidden-tab restore falls back to Dashboard.
- G4 no-regression: in Pro mode the tab set + behavior is byte-identical to today
  (Pro = current app). Existing 385 tests still green.
- G5 subtitles/banner/hint render without layout breakage at the 1200x700 min window.

## Stop conditions
- If removeTab/addTab reuse causes signal-wiring duplication (currentChanged firing
  twice): stop, dedupe the connection, don't paper over with guards.
- If any Pro tab holds state that breaks on remove/re-add (timers, threads): stop,
  hide via setTabVisible (Qt 5.15+/6) instead of remove, document which tabs needed it.

## Annotated imperfections (known at authoring)
- Color-blind safety of the green/red winrate palette is a SEPARATE issue (add a
  second channel: number + glyph) — noted in the UX assessment, not in this spec's scope.
- This spec is IA/guidance only; it does not add a guided tutorial (deferred).

## Open questions for the user
1. Existing users (DB with saved decks / match history) — default them to Pro (no change
   for you) or Basic (see the new front door once)? Recommend: Pro for existing, Basic
   for fresh.
2. Verification needs eyes on the running PyQt app (render can't be checked from the
   Cowork sandbox) — screenshot pass required before marking SHIPPED.
