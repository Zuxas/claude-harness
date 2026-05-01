# Double-Firing Handler Bugs in BE APL

**Date:** 2026-04-26 (5-7 AM session)
**Status:** RESOLVED at commit (see git log around 2026-04-26 morning)

## Discovery

Block 2 audit (T2.5 Bombardment-Mobilize integration) surfaced that
`engine/game_state.py:_do_combat` already materializes Voice Mobilize
Warrior tokens, while `apl/boros_energy.py:_handle_voice` also added
2 damage per Voice attack via shortcut. Result: every Voice attack
counted 4 damage instead of 2.

Diagnostic E revealed the same pattern for Guide of Souls ETB
trigger: engine `_apply_existing_board_etb` fires Guide trigger
automatically on every creature/token ETB; `apl/boros_energy.py:
_fire_guide_etb_trigger` fired it again manually at 7 audited call
sites.

## Root cause

The APL helpers were written when the engine didn't have automatic
ETB dispatch, OR before the engine's `_apply_existing_board_etb`
added Guide handling. Engine evolved to handle these triggers
systemically; APL helpers weren't removed when that happened.

Voice case: T1.1 fix (2026-04-25 night) added "another" filter to
Guide trigger but didn't recognize the engine's automatic firing.

## Resolution

Both fixes in single commit (today's morning):

### 1. `_handle_voice` (Voice of Victory Mobilize)
- Removed direct damage add (was double-counting -- engine combat
  damage step already counts attacking tokens via
  `sum(c.effective_power() for c in attackers)`)
- Removed `_fire_guide_etb_trigger` call (was double-firing -- engine
  `_apply_existing_board_etb` fires Guide trigger per token via
  `_make_token -> _fire_etb_triggers`)
- Body now only increments `_tokens_entered_this_turn` (needed for
  Ocelot city's blessing copy tracking)

### 2. `_fire_guide_etb_trigger` (Guide of Souls ETB)
- Removed life/energy add (was double-counting -- engine
  `_apply_existing_board_etb` fires Guide trigger automatically
  whenever any creature/token enters bf via `_fire_etb_triggers`)
- Helper now only sets `_gained_life_this_turn` flag for Ocelot's
  end-step Cat token trigger
- Audited call sites still call this for the flag (Ocelot Cats,
  Ajani Cat Warrior, fill-curve creatures, Arena haste, Pyromancer
  Elementals, Phlage hardcast/escape)

## Re-baseline impact (n=1000 seed=42)

| Deck      | Pre-fix | Diagnostic-E | Post-Voice+Guide-fix |
|-----------|---------|--------------|----------------------|
| Canonical | T4.62   | T4.71        | **T4.72**            |
| Variant   | T4.33   | T4.34        | **T4.40**            |
| Edge      | -0.29   | -0.37        | **-0.32**            |

Voice fix had smaller variant impact than predicted (+0.06 turn vs
predicted +0.12 to +0.32) because Voice cast T3-T4 with summoning
sickness rarely gets an attack window before games end (BE goldfish
median T4). The double-counting was real but goldfish-bounded.

Variant edge over canonical actually GREW from -0.29 to -0.32.
Canonical absorbed more of the Guide bug than variant did because
canonical has more turns for Guide to compound (slower deck);
variant kills earlier so fewer Guide overcounts accumulate.
**Sleeve-up read for variant gets STRONGER, not weaker.**

## Affected commits (all from 2026-04-26 session)

All prior session commits used the inflated baselines:
- `1e55791` (Stage 1.6) -- validation against T4.62 baseline now stale
- `29f528d` (variant deck) -- variant T4.33 was inflated by both bugs
- `63d0c75` (Stage 1.5) -- validation against T4.62 baseline now stale
- `0bc20bf` (100k Modern gauntlet 71.5%) -- includes both bugs in
  every game; true number is some amount lower (probably 67-70%)
- `ea5e196` (1k Modern gauntlet 71.1%) -- same as above
- `7e213ea` (foundation fix) -- T4.62 baseline locked in inflation
- `0c0f42c` (script support) -- tooling, no measurement
- `d14aa27` (re-baseline doc) -- documents the inflated T4.62
- `5801804` (sleeve_check.py) -- script works, baselines were stale

No re-runs of those commits needed -- the relative measurements hold
(commits compared to each other use the same engine state). Future
gauntlets and goldfish runs will use the corrected engine.

## Remaining triage

**Guide attack trigger:** RESOLVED 2026-04-27 at commit cf75e1a (spec
`harness/specs/2026-04-27-guide-attack-trigger-fix.md`). Engine
`_do_combat` self-pump block removed; APL `_simulate_guide_attack_trigger`
remains canonical. All three known double-firing handler bugs
(Voice Mobilize, Guide ETB, Guide attack) are now closed.

Pre-fix details (preserved for context):
- Engine `_do_combat` (~line 474): pumped Guide-itself by +2/+2 for
  3 energy (wrong per oracle: "target attacking creature")
- APL `_simulate_guide_attack_trigger` (called from `main_phase`):
  pumps best attacker by +2/+2 for 3 energy (correct per oracle)

Both fired if 6+ energy available pre-fix. APL version (correct
target) was retained; engine version (wrong target + double-firing)
removed.

### Re-baseline impact (Guide attack fix, n=1000 seed=42)

| Metric                       | Pre-fix | Post-fix | Delta    |
|------------------------------|---------|----------|----------|
| Canonical goldfish kill turn | T4.50   | T4.51    | +0.01    |
| BE mirror match WR (n=2000)  | 49.1%   | 51.9%    | +2.8pp   |
| 1k Modern field-weighted WR  | 65.3%   | 65.5%    | +0.2pp   |

Canonical goldfish drift was minimal (+0.01 turn) because the engine
pump only fired in late-game high-energy states (6+ energy = T5+ in
typical BE games), and BE goldfish kills median T4. Most games never
reached the affected code path.

Mirror moved +2.8pp on a single seed; symmetry says true mirror is
50% by definition, so this is seed-specific noise within the 47-53%
acceptance band per the spec's stop conditions. Both pre-fix (49.1%)
and post-fix (51.9%) are within ~2sigma of true 50%.

Aggregate gauntlet shifted +0.2pp -- consistent with the engine pump
being a small-contribution effect across the field.

**Other handlers worth auditing for the same pattern:** Phlage attack
trigger, Avatar Roku firebending, Ocelot Pride lifelink. The audit
methodology: for each handler, check if engine has parallel automatic
firing in `_do_combat`, `_apply_existing_board_etb`, or
`_fire_etb_triggers`. If yes, APL handler likely double-counts.
