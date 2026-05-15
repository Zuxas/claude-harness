# Execution Chain — 2026-05-15 (Friday)

**Authored:** 2026-05-14 end-of-day
**Sub-project focus:** RC DC prep (14 days out)
**Yesterday's haul:** 18+ features shipped across mtg-meta-analyzer.
The whole MTGA Player.log → match_log → Match History pipeline is now
end-to-end. Auto-import, auto-classify, auto-create-deck on unknown,
per-game SB plans, per-game life trajectory + classifier, opening
hand snapshots, full annotation-driven Watch Replay popup (cards,
abilities, targets, scry top/bottom, counterspell attribution),
mulligan analysis UI with empirical W-L per mull bucket, MTGA rank
progression on Dashboard. Plus Mythic decklist ingestion BIG FEATURE
(auto-fetch + parse + Save-to-My-Decks). Plus harness IMPERFECTIONS
cleanup. Plus M/W/F pipeline wire-in for 3 stale scrapers + Spicerack
400 fix + the MTGDecks Cloudflare hard-block discovery.

---

## Section 0 — Session start (15min)

Per `harness/CLAUDE.md` SESSION START PROTOCOL:

1. Read `harness/state/latest-snapshot.md` (regenerates at 04:30).
2. Read `harness/inbox/drift-pr--2026-05-15.md` if present.
3. Read `harness/MEMORY.md` — 2026-05-14 entry: huge build day.
4. Check `harness/IMPERFECTIONS.md` — closed two yesterday
   (grinding_breach + duplicate-deck-files), but plenty of mtg-sim
   engine items still open.
5. **Manual GUI smoke** — none of yesterday's work has been visually
   smoke-tested. Open the GUI, walk through My Decks → Tokyo Prowess
   → Match History sub-tab. Click a Bo3 match row, verify the Match
   Detail panel + Watch Replay popup render correctly. Note any
   layout / rendering bugs.
6. Run DAILY RHYTHM CHECK: present today's chain options A/B/C below.

---

## Today's chain — pick one

### Option A — Full day (6-8h) — Tokyo Prowess SB plan validation

The deck the user is taking to RC DC. Now that we have empirical
match_log_sb_plans data + the matchup_matrix Bo3 source data, validate
the team's current Tokyo Prowess SB plans against what actually wins.

1. **GUI smoke + bugfix sweep** (~30min). Walk every new surface from
   yesterday. Likely small rendering tweaks. Fix on the spot.

2. **Manual SB plan validation in Match History** (~1.5h). Open My
   Decks → Tokyo Prowess → Match History. For each of the 6 distinct
   opponent archetypes Jermey played yesterday, click into the Bo3
   matches, read the SB plans actually used, compare against the
   documented plans in `Team Resolve/rcdc_prowess_sb_plans.md`. Note
   any deltas. Update the canonical sheet for anything that
   consistently differed.

3. **Run gauntlet with current SB-plan-aware build** (~1-2h). With
   the per-game SB plan capture now writing match_log_sb_plans, the
   gauntlet runner can be informed by real plans rather than just
   blunt sideboarding. `python parallel_launcher.py --deck
   izzetprowessstandardtokyo --field rcdc` (verify the gauntlet picks
   up the latest mainboard from saved_decks.id=17). Sample size 1000.

4. **EV vs Field projection refresh** (~30min). My Decks → Tokyo
   Prowess → EV vs Field. After yesterday's all-formats fix + the
   Untapped data refresh, the matchup data should be fresher. Capture
   the new headline EV number. Compare to the locked 2026-05-01 baseline.

5. **Pivot if data weird** (~varies). If the gauntlet shows >5pp
   shift from the 2026-05-01 baseline, investigate — is it new meta
   shift (real signal) or a data-quality issue (the recent Untapped
   wide-window pull may have brought in stale data)?

6. **End of day** (~30min). Author 2026-05-16 chain. Update
   NEXT_STEPS / CLAUDE.md / ROADMAP.

### Option B — Focused (~4-5h) — GUI smoke + one targeted RC item

If energy is moderate.

1. Section 0
2. GUI smoke + bugfix sweep (1h)
3. ONE of: gauntlet run OR SB plan validation OR EV refresh (~2-3h)
4. End of day (15min)

### Option C — Conservative (~2-3h) — Pivot away from mtg-meta-analyzer

If the previous-day push left you wanting different scenery. Several
mtg-sim IMPERFECTIONS are still warm:
- `standard-apl-goldfish-only-no-match-quality` (12-16h, do one at a time)
- `standard-field-missing-dimir-excruciator-azorius-blink` (1h)
- Pioneer L1 backlog (57 cards, batched)

Or hop back into the harness — the skill-system spec at
`harness/specs/2026-05-01-skill-system-harness.md` is 14d stale.

---

## Loose ends from 2026-05-14

- **GUI smoke** has NOT been performed for any of yesterday's work.
  Top priority for today.
- **Voicemeeter startup shortcut** decision still parked (skipped twice).
- **MTGDecks Cloudflare hard-block** — IP-level deny, no scraper
  fixes it. Wait 24-72h for reputation to expire, or use VPN/proxy.
- **Match 66 (ViewtifulYosh) misclassification** — user confirmed
  intentional (was actually Dimir, not Tokyo Prowess as I initially
  thought). No action needed.
- **The 5/15 chain doc dated 2026-05-15 was authored 5/14 8 AM and
  proved stale by lunchtime** — yesterday's session went 12h+ and
  shipped everything that chain had queued for today and more. So
  this doc is yet another stale-on-arrival snapshot; refresh
  expectations from the actual current state, not this doc.

---

## Open backlog (lower priority)

- **Rank progression chart on Dashboard** — `rank_snapshots` now has
  data, build a small line chart of season climb over time. ~45-60min.
  Visual ROI starts after a week of snapshots.
- **Cards-played-on-curve analysis** — uses the new replay annotation
  data to flag turns where you didn't spend on-curve mana. ~45-60min.
  Useful for matchup post-mortem.
- **Damage breakdown by source** — replay annotations give per-source
  damage; aggregate per deck to surface "which threats are carrying
  your wins." ~30-45min.
- **Visual board replay viewer (v0.7+)** — advisor flagged 6-10h for
  the state machine; deferred until post-RC.
- **Cosmetic spec omissions from variant-tracking** — extract
  _load_variants to db layer (done yesterday), format-filtered deck
  dropdown (done yesterday), unused `skipped_already_resolved` counter
  (done yesterday). Note: these are all DONE already.
- **PyInstaller .exe packaging** — defer until post-RC.

---

## Sub-project menu (per harness/SUBPROJECTS.md)

If user pivots away from mtg-meta-analyzer at the morning DAILY
RHYTHM CHECK, surface these:

- **mtg-sim** — Phase 3.5 keyword coverage Stages D-K (no event
  pressure); Standard match APLs (IMPERFECTION
  standard-apl-goldfish-only-no-match-quality).
- **harness** — Skill-system spec at
  `harness/specs/2026-05-01-skill-system-harness.md` (14d stale).
- **APLs** — Pioneer L1 backlog (57 cards in waves of 8-12).
- **website** — Latent.
- **calibration** — Stable.

---

## Standing-by note

Per Rule 7 of SPEC-FIRST EXECUTION PROTOCOL: after each chain item,
surface options (continue / pivot / take a break / drift-detect
snapshot). Do not nudge toward bedtime or toward continuing. User
decides.

14 days to RC DC. Pace accordingly.
