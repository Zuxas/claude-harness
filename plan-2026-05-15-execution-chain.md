# Execution Chain — 2026-05-15 (Friday)

**Authored:** 2026-05-14 end-of-day
**Sub-project focus:** mtg-meta-analyzer (RC DC 5/29-5/31 prep arc)
**Days to RC DC:** 14
**Primary ask going in:** Untapped Mythic decklist ingestion (the "big feature" the user explicitly asked for at end-of-day 2026-05-14).

---

## Section 0 — Mandatory Session-Start (15min)

Per `harness/CLAUDE.md` SESSION START PROTOCOL:

1. Read `harness/state/latest-snapshot.md` (regenerated 04:30).
2. Read `harness/inbox/drift-pr--2026-05-15.md` if present (Gemma 04:50).
3. Read `harness/MEMORY.md` — 2026-05-14 entry: huge day. Match Log variant tracking shipped + merged + hotfixed; "May 11-12 RC" memory hallucination cleaned out of NEXT_STEPS / `project_rc_events.md`; calendar locked (ONLY RC DC 5/29-5/31 has Flight+Hotel=yes); Dashboard WR chart bug fixed (datetime axis, default mode); Ladder tab gained Mythic deck linkout; Untapped premium snapshot refreshed without `--last-7-days` (18 → 121 rows).
4. Check `harness/IMPERFECTIONS.md` for new entries since 2026-05-14.
5. Run DAILY RHYTHM CHECK: present today's chain options A/B/C below; wait for user pick.

---

## Today's chain — pick one

### Option A — Full day (7-9h) — Mythic decklist ingestion (BIG FEATURE)

The default. User asked for this explicitly at end-of-day 2026-05-14: "I want the big feature."

1. **Recon turn — find the Untapped decklist endpoint** (~30min).
   - Goal: given a `short_id` from `untapped_entries`, get the canonical decklist JSON.
   - First probe: `GET https://api.mtga.untapped.gg/api/v1/deck/<short_id>` with cookies (likely candidate based on REST conventions).
   - Second probe: `GET https://api.mtga.untapped.gg/api/v1/decks/<short_id>`.
   - Third probe: `GET https://api.mtga.untapped.gg/api/v1/upload-log/<short_id>` (known endpoint from `scrapers/UNTAPPED_README.md`) — parse the embedded replay log for the player-side grpIds. Less precise (only sees cards that hit the board), but a known-working fallback.
   - **STOP after recon and surface findings.** Decide between API-decklist path (clean) and replay-parse fallback (already-validated technique from `untapped_opponent_classifier.py`).

2. **Build `scrapers/untapped_deck_fetcher.py`** (~1h).
   - `fetch_decklist(short_id) -> dict | None` returning `{"mainboard": {name: qty}, "sideboard": {name: qty}}`.
   - Cookie-authed (reuse the auth path from `untapped_premium_scraper.py`).
   - `grpId` → card name via `card_data.arena_id` lookup.
   - Unit tests with fixture replay JSON.

3. **Schema + writer** (~30min).
   - New table `untapped_decklists (short_id TEXT PRIMARY KEY, mainboard_json TEXT, sideboard_json TEXT, archetype TEXT, fetched_at TEXT)`.
   - Idempotent CREATE in a sibling of `db/untapped_queries.py` (or extend the existing module).
   - `save_decklist(short_id, mainboard, sideboard, archetype)` upsert helper.

4. **Batch trigger from the Ladder tab** (~30min).
   - "Fetch decklists for top 30" button on Ladder tab.
   - Calls fetcher for each leaderboard row that doesn't have a stored decklist.
   - Status bar shows progress (`Fetched 12/30…`). Worker thread, not blocking.

5. **Decklist panel below the Mythic leaderboard table** (~1-1.5h).
   - Click a leaderboard row → panel populates with mainboard / sideboard (two columns, qty + card name).
   - Use existing `gui/widgets/card_tooltip.py` for hover preview.
   - Right-click on a card → "View on Scryfall" (existing pattern).
   - Right-click on the leaderboard row → keep existing "Open deck on Untapped.gg" + "Copy deck URL", ADD "Save to My Decks" (copies into `saved_decks` table for direct comparison vs Tokyo Prowess).

6. **M/W/F pipeline integration** (~15min).
   - Add fetcher call to `scripts/run_fill_from_prefs.py` Untapped block (after the match_log writer).
   - Also: while we're in there, drop `--last-7-days` from the premium scraper line (the wider window had 6.7x more rows; flag suppresses upstream data we want).

7. **Tests** (~30min).
   - Fetcher mocked against fixture JSON or replay log.
   - Schema migration idempotency.
   - Save-to-my-decks flow.

8. **End-of-day** (~30min) — author 2026-05-16 chain, update CLAUDE.md / NEXT_STEPS / ROADMAP.

### Option B — Focused (~4-5h) — Ship the core feature, defer the polish

If energy is moderate. Ships the data ingestion + decklist panel; defers the "Save to My Decks" copy action + M/W/F pipeline auto-fetch.

1. Section 0
2. Recon turn (30min)
3. Build fetcher + schema (1.5h)
4. Build decklist panel below leaderboard (1.5h)
5. Tests (30min)
6. End-of-day (15min)

### Option C — Conservative (~2-3h) — Recon + sharper RC EV

If recon turn reveals the API path is harder than expected, or energy is low. Pivots to the EV model item from yesterday's chain.

1. Section 0
2. Recon turn — figure out the right Untapped endpoint (30min). If clean answer found, write a 1-page spec doc for tomorrow. If dead end, file IMPERFECTION + pivot.
3. **RC-realistic field model in `analysis/deck_ev.py`** (2-3h) — replace 14d paper-meta default with RCQ-weighted blend (recent RCQ top-8s 0.5 + Untapped Mythic Bo3 0.3 + paper meta 0.2). New `RCQ_BLEND_FIELD` constant, "Field source" dropdown on EV vs Field sub-tab.
4. End-of-day (15min)

---

## Loose ends from 2026-05-14

- **Voicemeeter startup shortcut deletion** still pending (from 5/13). `Startup\Voicemeeter (VB-Audio).LNK` exists; either delete or leave.
- **Manual GUI smoke of variant-tracking** — user opened the tab post-hotfix but didn't walk through the full Log Match dialog + Sync Untapped + Resolve flow. Option A item 5 (the decklist panel) lives next to the Match Log feature so smoke happens naturally as side effect.
- **Power plan stays on AMD Ryzen High Performance** (set 2026-05-13). Watch for Windows-update regressions.

---

## Open IMPERFECTIONS / spec backlog (lower priority)

Tracked in NEXT_STEPS.md (mtg-meta-analyzer) and `harness/IMPERFECTIONS.md`:

- **Direction C arc** (design language pass + tab reorg) — DO NOT START YET. Wait for one week of palette-recents data first (target ~2026-05-20). Spec authoring after that.
- **Tokyo Prowess SB 1-page printout** — listed in NEXT_STEPS, not on critical path.
- **Standard match APLs** (cross-repo mtg-sim) — IMPERFECTION `standard-apl-goldfish-only-no-match-quality`. Not on this week's critical path.
- **PyInstaller .exe packaging** — defer until post-RC.
- **Cosmetic spec omissions from variant-tracking** (followups dropped from the 5/14 ship): extract `_load_variants` to db layer; format-filtered deck dropdown in `_MatchDialog`; unused `skipped_already_resolved` summary counter. None blocking.

---

## Sub-project menu (per harness/SUBPROJECTS.md)

If user pivots away from mtg-meta-analyzer at the morning DAILY RHYTHM CHECK, surface these:

- **mtg-sim** — Phase 3.5 keyword coverage Stages D-K (no event pressure); Standard match APLs.
- **harness** — Skill-system spec at `harness/specs/2026-05-01-skill-system-harness.md` (scheduled 2026-05-05, never started; ~13d stale).
- **APLs** — Pioneer L1 backlog.
- **website** — Latent.
- **calibration** — Stable.

---

## Standing-by note

Per Rule 7 of SPEC-FIRST EXECUTION PROTOCOL: after each chain item, surface options (continue / pivot / take a break / drift-detect snapshot). Do not nudge toward bedtime or toward continuing. User decides.

14 days to RC DC. Pace accordingly.
