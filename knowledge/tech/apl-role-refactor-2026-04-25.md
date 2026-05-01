---
title: "APL Role-Based Refactor — BorosEnergy reference impl + IzzetProwess template"
domain: "tech"
last_updated: "2026-04-25"
confidence: "high"
status: "spec — Phase 1+2 complete on BorosEnergyAPL; template for IzzetProwess and other hand-tuned APLs"
sources: ["conversation", "apl/boros_energy.py", "apl/aggro_base.py", "engine/keywords.py", "data/card.py"]
---

## Summary

`BorosEnergyAPL` currently hardcodes 14 card-name constants (`RAGAVAN`,
`OCELOT_PRIDE`, `PHLAGE`, etc.) and the entire turn loop iterates by name
(`for name in (RAGAVAN, SCREAMING_NEMESIS):`, `if card.name == AJANI:`).
Swap any one card for a variant — Monastery Swiftspear instead of Ragavan,
Lightning Helix instead of Phlage's escape line, a different one-drop —
and a piece of logic silently goes dead.

Phase 1 refactor: the APL infers card *roles* (haste threats, lifegain
sources, sac outlets, face burn, etc.) from the loaded deck via oracle
text + already-populated KWTags, then drives the turn loop by role
queries instead of name comparisons. Net result: a BE variant with new
threats / new burn / dropped Phlage plays correctly with **zero APL code
changes**.

**Status as of 2026-04-25 night: Phase 1 (stages 1-7) and Phase 2
(stages 1-3) are complete on BorosEnergyAPL.** The reference implementation
ships in `apl/boros_energy.py` across commits 9de316f → 81470f8. This
doc is now the template for applying the same pattern to other hand-tuned
APLs (IzzetProwess next; see "When to apply this pattern" below).

## Content

### Why this matters

The Pro Tour is May 1-3. Post-PT Standard meta will reshape, and Modern
Boros Energy is also seeing experimental brews (Monastery Swiftspear
splits, post-Cori-Steel-Cutter shells, Phlage cuts for more burn). Each
variant currently requires editing `boros_energy.py` to re-wire which
cards the turn loop knows about. With role detection, the same APL
plays every BE variant correctly without manual intervention.

The pattern also generalizes — once it works for BE, it's the template
for refactoring `IzzetProwessAPL`, `AmuletTitanAPL`, and the other
hand-tuned APLs that face the same brittleness.

### Architectural pattern

`get_apl()` (in `apl/__init__.py`) calls `cls()` with no arguments, so
the APL doesn't know its deck at `__init__`. But the deck IS visible
on the first call to `keep()` / `main_phase()` via the GameState. So:
**lazy-compute role membership the first time the APL is invoked,
cache it on the instance, query roles thereafter.**

Source the deck cards from `gs.zones` (library + battlefield + hand +
graveyard at game start). Cache on instance via a `_roles_computed`
guard.

### Architectural choice — individual call positions, NOT unified dispatch

**This is the most important "lesson learned" from BE Phase 1+2 — read
before applying the pattern to a second APL.**

The natural next step after extracting per-card handlers (Phase 1 stage
5) is to consolidate handler dispatch into a single loop per phase:

```python
# Tempting but WRONG for tight drift bounds:
def main_phase(self, gs):
    for card_name, handler_name in self.SPECIAL_MECHANICS.items():
        if card_name in self._deck_names:
            getattr(self, handler_name)(gs, phase='main')
```

**Don't do this for main_phase / main_phase2.** The existing handler
calls are interleaved with role-driven loops (haste cast → Arena handler
→ sac outlet cast → Ajani handler → Guide handler → Galvanic cast).
Moving all 3 main_phase handlers into a single dispatch position changes
their order relative to the role-driven loops, which IS a behavior change
exceeding the tight drift bound (±0.05 turn for Phase 2-style refactors).

**The right pattern:**

1. Keep individual `if "<Card Name>" in self._deck_names: self._handle_<card>(gs, '<phase>')`
   calls in their existing positions in main_phase / main_phase2.
2. Use the unified dispatch helper `_dispatch_special_mechanics(gs, phase)`
   ONLY for new phases where ordering doesn't already exist (combat,
   end-step, etc.).

The dispatch helper still has architectural value — it makes new
combat-phase or end-phase handlers land for free without modifying
`_simulate_combat_triggers` or `_simulate_end_step` further. Voice of
Victory's Mobilize trigger uses this exact path: added to
SPECIAL_MECHANICS dict, handler self-gates on `phase='combat'`, fires
automatically when `_simulate_combat_triggers` calls
`_dispatch_special_mechanics(gs, 'combat')`.

### Pre-existing infrastructure (verified 2026-04-25)

- `data/card.py` Tag enum has `THREAT`, `REMOVAL`, `CANTRIP` defined
  but **unpopulated** — they exist as enum members, no code sets them
  based on oracle text. Phase 1 doesn't depend on them; it computes
  role buckets directly from oracle text + KWTags.
- `engine/keywords.py` `KWTag` ARE auto-populated by `tag_keywords(card)`
  during deck load. So `KWTag.HASTE in c.tags` is reliable — no need
  to parse "haste" out of oracle text for keyword-only roles. Verified
  earlier this session (Ranger-Captain card object had
  `tags = {'creature', 'three_drop', 'hate_bear'}` after deck load).
- `apl/aggro_base.py` `AggroAPL(SBPlanMixin, BaseAPL)` already
  demonstrates the class-attribute pattern (`CREATURES`, `BURN_SPELLS`,
  `HASTE_CREATURES`, `PUMP_SPELLS`). Subclasses override the attrs;
  the base class consults them at runtime. **Phase 1 follows the same
  shape but populates the buckets dynamically from the loaded deck
  instead of statically per subclass.**
- `engine/oracle_parser.py` exists in the WIP zone — **EXPLICITLY
  EXCLUDED** from Phase 1. Use raw `c.oracle_text.lower()` string
  matching instead. Robust enough for the role buckets needed; no
  WIP dependency.

### Phase 1: the `_compute_roles` method

```python
class BorosEnergyAPL(BaseAPL):
    name = "Boros Energy"
    win_condition_damage = 20
    max_turns = 12

    _roles_computed = False  # guard for lazy compute

    def _compute_roles(self, deck_cards):
        """Scan the loaded 75 once, bucket each card by inferred role.
        After this runs, the turn loop queries roles, not names."""
        from data.card import Tag
        from engine.keywords import KWTag

        deck_names = {c.name for c in deck_cards}

        def _otext(c):
            return (c.oracle_text or "").lower()

        # Haste threats: creatures MV ≤ 2 with haste (KWTag or oracle)
        # Picks up Ragavan, Screaming Nemesis, Monastery Swiftspear,
        # Slickshot Show-Off, anything else with haste at MV ≤ 2.
        self.haste_threats = {
            c.name for c in deck_cards
            if c.has(Tag.CREATURE) and c.cmc <= 2
            and (KWTag.HASTE in c.tags or "haste" in _otext(c))
        }

        # Lifegain sources: KWTag.LIFELINK or any "you gain"/"gain life"
        # phrase in oracle. Picks up Ocelot Pride (lifelink), Phlage
        # (gain 3), Lightning Helix, Guide of Souls.
        self.lifegain_sources = {
            c.name for c in deck_cards
            if KWTag.LIFELINK in c.tags
            or any(p in _otext(c) for p in ("you gain", "gain life",
                                             "gains life"))
        }

        # Token producers: oracle says "create" + "token". Picks up
        # Ajani, Pyromancer (when discarding nonlands), Voice of Victory.
        self.token_producers = {
            c.name for c in deck_cards
            if "create" in _otext(c) and "token" in _otext(c)
        }

        # Energy sources: oracle mentions energy ({E} or word). Picks up
        # Guide of Souls, Galvanic Discharge, Static Prison.
        self.energy_sources = {
            c.name for c in deck_cards
            if "{e}" in _otext(c) or "energy" in _otext(c)
        }

        # Sac outlets: "sacrifice a creature" + activated cost (":")
        # in oracle. Picks up Goblin Bombardment, anything similar.
        self.sac_outlets = {
            c.name for c in deck_cards
            if "sacrifice a creature" in _otext(c)
            and ":" in _otext(c)
        }

        # Face burn: instants/sorceries that "deal X damage to any
        # target". Picks up Lightning Bolt, Lightning Helix.
        # NOTE: Phlage is NOT in here even though it deals damage —
        # it's a creature, not an instant/sorcery. The has_phlage
        # flag below routes Phlage through its dedicated handler.
        self.face_burn = {
            c.name for c in deck_cards
            if (c.has(Tag.INSTANT) or c.has(Tag.SORCERY))
            and "damage to any target" in _otext(c)
        }

        # All creatures, sorted by CMC ascending, name as tiebreak.
        # Used by the fill-curve loop in main_phase2 to deploy
        # cheapest-first. Replaces the current implicit min(cmc, name)
        # ordering.
        self.creatures_by_cmc = sorted(
            {c.name for c in deck_cards if c.has(Tag.CREATURE)},
            key=lambda n: (
                next(c.cmc for c in deck_cards if c.name == n),
                n,
            ),
        )

        # Special-mechanic flags — these gate dedicated handlers for
        # cards whose mechanics are unique enough that oracle-pattern
        # detection won't capture them correctly. The handler is called
        # only if the card is in the deck; absence doesn't break the
        # turn loop.
        self.has_phlage          = "Phlage, Titan of Fire's Fury" in deck_names
        self.has_ajani           = "Ajani, Nacatl Pariah" in deck_names
        self.has_ocelot          = "Ocelot Pride" in deck_names
        self.has_guide           = "Guide of Souls" in deck_names
        self.has_arena_of_glory  = "Arena of Glory" in deck_names
        self.has_bombardment     = "Goblin Bombardment" in deck_names
        self.has_pyromancer      = "Seasoned Pyromancer" in deck_names

        self._roles_computed = True

    def _ensure_roles(self, gs):
        """Call from the entry points (keep, main_phase, main_phase2,
        bottom). Sources deck cards from gs.zones on first call."""
        if self._roles_computed:
            return
        # Game-start state: library + hand + battlefield + graveyard
        # equals the full 60-card mainboard (sideboard excluded — APL
        # doesn't see SB during a goldfish run).
        deck_cards = (list(gs.zones.library) + list(gs.zones.hand)
                      + list(gs.zones.battlefield)
                      + list(gs.zones.graveyard))
        self._compute_roles(deck_cards)
```

### SPECIAL_MECHANICS dict (Phase 1)

For cards whose mechanics don't reduce to oracle-text patterns, keep
dedicated handlers — but registered in a class-level dict, not
hardcoded in the turn loop. **Each handler is gated on the
corresponding `has_<card>` flag** so absence is silent.

```python
class BorosEnergyAPL(BaseAPL):
    # ... role-detection above ...

    # Dedicated handlers for cards with unique mechanics that
    # oracle-text patterns can't capture cleanly.
    SPECIAL_MECHANICS = {
        "Phlage, Titan of Fire's Fury":
            ("has_phlage", "_handle_phlage"),
        "Ajani, Nacatl Pariah":
            ("has_ajani", "_handle_ajani_etb"),
        "Ocelot Pride":
            ("has_ocelot", "_handle_ocelot_end_step"),
        "Guide of Souls":
            ("has_guide", "_handle_guide_attack_pump"),
        "Arena of Glory":
            ("has_arena_of_glory", "_handle_arena_exert_haste"),
        "Goblin Bombardment":
            ("has_bombardment", "_handle_bombardment_finish"),
        "Seasoned Pyromancer":
            ("has_pyromancer", "_handle_pyromancer_loot"),
    }

    def _run_special_mechanics(self, gs, phase):
        """Call each registered handler that's flagged-present.
        phase = 'main' | 'combat' | 'main2' | 'end'."""
        for card_name, (flag_attr, method_name) in self.SPECIAL_MECHANICS.items():
            if getattr(self, flag_attr, False):
                handler = getattr(self, method_name, None)
                if handler is not None:
                    handler(gs, phase)
```

Each `_handle_*` method internally checks `gs.phase` (or accepts a phase
arg) and decides whether to fire. Phlage hardcast / Phlage escape stay
inside `_handle_phlage`. Ajani ETB stays inside `_handle_ajani_etb`. Etc.

### Refactor pattern: before / after

#### `keep()` — minor changes

Existing logic uses `RAGAVAN` constant for the on-the-play keeper
heuristic and `Tag.ONE_DROP` for one-drop count. After:

```python
def keep(self, hand, mulligans, on_play):
    self._ensure_roles(self._first_seen_gs)  # see _ensure_roles note below
    lands = [c for c in hand if c.is_land()]
    creatures = [c for c in hand if c.has(Tag.CREATURE)]
    haste = [c for c in hand if c.name in self.haste_threats]
    # ... rest unchanged structurally ...

    # OLD: if any(c.name == RAGAVAN for c in hand) and len(lands) >= 1: return True
    # NEW: any haste threat is a comparable on-the-play keeper signal
    if haste and len(lands) >= 1: return True
```

> `_ensure_roles` needs a GameState to source cards. `keep()` runs
> *before* the GameState is alive in the current `base_apl.py` flow.
> Two options: (a) defer role compute until first `main_phase` call
> (then `keep()` falls back to a less-informed heuristic that doesn't
> reference role buckets — acceptable since `keep()` is rare in goldfish);
> (b) restructure `base_apl.run_game` to construct GameState earlier
> and pass it to `keep()`. **Phase 1 picks (a) for minimal scope.**
> The keeper heuristic in (a) loses the haste-threat shortcut but
> keeps the land/creature/dead-card heuristics intact.

#### `main_phase()` — pre-combat

```python
def main_phase(self, gs):
    from engine.keywords import KWTag
    self._ensure_roles(gs)

    self._gained_life_this_turn = False
    self._tokens_entered_this_turn = 0

    # Treasure mana (unchanged)
    if self._treasures > 0:
        ...

    # 1. Land
    self._play_land_if_able(gs)

    # 2. Haste creatures pre-combat — was: for name in (RAGAVAN, NEMESIS)
    #    Now: iterate over auto-detected role bucket.
    for card in list(gs.hand()):
        if (card.name in self.haste_threats
                and gs.mana_pool.can_cast(card.mana_cost, card.cmc)):
            gs._log(f"  [PRE-COMBAT] {card.name} (haste, role-detected)")
            gs.cast_spell(card)
            break

    # 3. Sac outlet pre-combat — was: if card.name == GOBLIN_BOMBARD
    for card in list(gs.hand()):
        if (card.name in self.sac_outlets
                and gs.mana_pool.can_cast(card.mana_cost, card.cmc)):
            gs.cast_spell(card)
            break

    # 4. Special mechanics — Arena of Glory exert, Ajani pre-combat,
    #    Guide attack-trigger pump, Galvanic energy gain
    self._run_special_mechanics(gs, phase="main")

    # 5. Energy-source spells — was: if card.name == GALVANIC
    #    NEW: any energy_source instant cast for energy gain
    for card in list(gs.hand()):
        if (card.name in self.energy_sources
                and (card.has(Tag.INSTANT) or card.has(Tag.SORCERY))
                and gs.mana_pool.can_cast(card.mana_cost, card.cmc)):
            # Energy-spell logic moves into a handler that knows
            # the specific spell — kept as a local dispatch:
            self._cast_energy_spell(gs, card)
```

#### `main_phase2()` — post-combat

Replace the explicit priority tuple
`(OCELOT_PRIDE, GUIDE_OF_SOULS, AJANI, VOICE_OF_VICTORY, RAGAVAN)`
with role-based deployment:

```python
def main_phase2(self, gs):
    from engine.keywords import KWTag
    self._ensure_roles(gs)

    # Combat triggers (Ragavan treasure, Phlage attack, Ocelot lifelink)
    # Role-detected: any haste threat that's now-attacking with KWTag
    # corresponding to its trigger. Phlage/Ocelot/Ragavan logic moves
    # into _run_special_mechanics(phase='combat').
    self._run_special_mechanics(gs, phase="combat")

    # Post-combat creature deployment — cheapest first via creatures_by_cmc.
    # OLD priority tuple is replaced by ordered iteration through the
    # role bucket. SPECIAL_MECHANICS handlers fire for unique cards.
    for name in self.creatures_by_cmc:
        for card in list(gs.hand()):
            if (card.name == name
                    and card.has(Tag.CREATURE)
                    and gs.mana_pool.can_cast(card.mana_cost, card.cmc)):
                gs.cast_spell(card)
                # Guide trigger if any guide on bf
                if self.has_guide:
                    self._handle_guide_etb_trigger(gs, card)
                break

    # Phlage hardcast and Phlage escape — only if has_phlage.
    # PRESERVE the CMC=0 kludge gated on the flag.
    if self.has_phlage:
        self._handle_phlage_hardcast_and_escape(gs)

    # Pyromancer loot — only if has_pyromancer.
    if self.has_pyromancer:
        self._handle_pyromancer_loot(gs)

    # Face burn — was: for card in list(gs.hand()) if card.name == LIGHTNING_BOLT
    #    NEW: any face_burn instant/sorcery castable.
    for card in list(gs.hand()):
        if (card.name in self.face_burn
                and gs.mana_pool.can_cast(card.mana_cost, card.cmc)):
            gs.cast_spell(card)
            gs.damage_dealt += int(self._face_burn_dmg(card))
            gs._log(f"  Face burn ({card.name}): "
                    f"{self._face_burn_dmg(card)} dmg "
                    f"({gs.damage_dealt} total)")

    # End step (Ocelot tokens, etc.)
    self._run_special_mechanics(gs, phase="end")

    # Bombardment lethal check — only if has_bombardment.
    if self.has_bombardment:
        self._handle_bombardment_finish(gs)
```

`_face_burn_dmg(card)` is a small helper that parses the damage value
out of the oracle text: `"deal 3 damage"` → `3`. Use a regex like
`r"deals?\s+(\d+)\s+damage"`. If multiple matches, take the first.

### CRITICAL: Phlage CMC=0 kludge — must preserve

Current BE APL has this in `main_phase2`:

```python
# Phlage — hardcast {1}{R}{W}: 3 damage + 3 life, then SACRIFICE
# Scryfall data is bugged (CMC 0) so we check mana manually
for card in list(gs.hand()):
    if card.name == PHLAGE and gs.mana_pool.can_pay("{1}{R}{W}", 3):
        gs.mana_pool.pay("{1}{R}{W}", 3)
        ...
```

This kludge MUST move into `_handle_phlage_hardcast_and_escape` and run
verbatim, gated only on `self.has_phlage`. **Do not** try to fix the
underlying CMC=0 bug as part of this refactor — that's a card_db /
Scryfall data issue, separate scope.

### Validation protocol — ACTUAL RESULTS (BE reference)

#### Pre-refactor baseline (Stage 1, commit 9de316f)

Re-baseline run done first because `ARCHITECTURE.md:117` cited stale
T4.92 (2026-04-09 vintage, predates engine WIP push). 1000-game
canonical, seed=42:

  WR:           99.9%
  Avg kill:     T4.59
  Median:       T4
  T4 % exact:   47.3%
  By T4 (cum):  52.3%
  By T5 (cum):  88.2%

This is the comparison baseline for the role-refactor. ARCHITECTURE.md
updated with both 2026-04-09 historical line and 2026-04-25 current
line for drift-tracking record.

#### Phase 1 final result (after stage 5, commit b5e6bb9)

1000-game canonical, seed=42:

  WR:           100.0%   (drift +0.1pp vs baseline ✓ within ±2%)
  Avg kill:     T4.48    (drift -0.11 turn vs T4.59 ✓ within ±0.2)
  Median:       T4       (unchanged ✓)
  T4 % exact:   52.3%    (drift +5pp vs 47.3% ✓ AT upper bound of ±5pp)
  By T4 (cum):  57.0%    (drift +4.7pp)
  By T5 (cum):  92.7%    (drift +4.5pp)

All within drift bounds. Drift direction is positive (faster, more T4
wins) — likely cause: role-driven main_phase2 loop changes creature
cast order so Guide-of-Souls fires earlier in post-combat, triggering
more lifegain/energy on subsequent ETBs.

#### Phase 2 final result (after stage 3, commit 81470f8)

1000-game canonical, seed=42:

  WR:           100.0%   (IDENTICAL to Phase 1 final)
  Avg kill:     T4.48    (IDENTICAL)
  Median:       T4       (IDENTICAL)
  T4 % exact:   52.3%    (IDENTICAL)
  By T5 (cum):  92.7%    (IDENTICAL)

Phase 2 (dict simplification + dispatch helper + Voice handler) is
provably zero-drift on canonical. The ±0.05-turn bound is met exactly
because the architectural choice above (individual call positions for
main_phase / main_phase2) preserves canonical play unchanged. The new
dispatch helper only fires for combat-phase Voice handler, which is
gated on Voice being in the deck (Voice not in canonical = no-op).

#### Field-weighted gauntlet baseline

`88.8% FWR` (post-2026-04-22 N=500 modern-tuning audit, before role
refactor). Goldfish drift positive (faster) suggests gauntlet WR may
also tick up slightly. Re-run gauntlet after role refactor lands for
all decks if you want updated FWR numbers.

#### Refactor validation steps

1. **Pre-refactor baseline run** (do this first, on current HEAD):
   - 1000-game goldfish on canonical `decks/boros_energy_modern.txt`
   - Record: WR, avg kill, median kill, T4 %, T5 %
   - Save snapshot: `data/be_pre_refactor_baseline_<DATE>.json`

2. **Smoke test after each commit during refactor**:
   - 100-game goldfish, confirm WR ≥ 95% and no exceptions
   - Skip if you're using a feature branch and committing in batches

3. **Post-refactor canonical validation**:
   - 1000-game goldfish on the same canonical 75
   - Compare against pre-refactor baseline
   - **Acceptable drift: ±2% WR, ±0.2 kill-turn, ±5% T4/T5 buckets**
   - If drift > acceptable, debug before committing. The refactor MUST
     be functionally equivalent on the canonical list.

4. **Variant stress test** — `decks/boros_energy_variant_test.txt`:
   ```
   // BE variant test - synthetic 2026-04-25
   // Stress test for role-based detection: Swiftspear instead of
   // Ragavan, Helix instead of one Phlage, Voice replacing Bombard+Charm.
   4 Monastery Swiftspear         <-- replaces 4 Ragavan
   4 Ocelot Pride
   4 Guide of Souls
   3 Phlage, Titan of Fire's Fury <-- was 4
   1 Lightning Helix              <-- replaces 1 Phlage
   4 Ajani, Nacatl Pariah
   2 Seasoned Pyromancer
   1 Ranger-Captain of Eos
   4 Galvanic Discharge
   1 Thraben Charm                <-- was 2
   2 Voice of Victory             <-- new
   1 Lightning Bolt
   2 Goblin Bombardment           <-- was 3
   2 Blood Moon
   2 The Legend of Roku
   // lands unchanged
   4 Arid Mesa
   4 Flooded Strand
   3 Arena of Glory
   3 Elegant Parlor
   3 Marsh Flats
   2 Sacred Foundry
   2 Plains
   1 Mountain
   1 Sunbaked Canyon

   Sideboard
   // sideboard unchanged from canonical
   ```

   - 1000-game goldfish on the variant
   - **Expected: WR within 5% of canonical** (variant is intentionally
     weaker — Swiftspear is worse than Ragavan, fewer Bombardments)
   - **Critical: avg-kill-turn stays sane (T4-T6 range, not T8+)**
     T8+ would indicate the APL is failing to deploy threats —
     proves role detection is broken.
   - **Critical: Swiftspear, Helix, Voice all show non-zero cast rate**
     (use the same monkey-patch trace technique from the Ranger-Captain
     smoke if needed). Validates each role bucket picked up the new card.

#### Variant test — ACTUAL RESULTS (Phase 1 stage 6, commit 7dcdbbd)

1000-game variant deck (`decks/boros_energy_variant_test.txt`), seed=42:

  WR:           100.0%   (matches canonical 100%, well within ±5%)
  Avg kill:     T4.79    (canonical T4.48, +0.31 — variant intentionally
                          weaker, plays sanely in T4-T6 range ✓)
  Median:       T5

  Cast counts (per 1000 games):
    Monastery Swiftspear: 819 (81.9%)  — haste_threats role
    Lightning Helix:       98 (9.8%)   — face_burn + lifegain (1-of)
    Voice of Victory:     368 (36.8%)  — token_producers / creatures_by_cmc

  All role-detected new cards casting. Pattern works.

#### Variant test — Phase 2 ACTUAL (commit 81470f8)

Same variant, post-Phase-2 (Voice Mobilize handler now active):

  WR:           100.0%
  Avg kill:     T4.73    (Phase 1 variant T4.79, -0.06 turn — Mobilize
                          damage contributing as expected)
  Voice cast:    367/1000 (36.7%)
  Voice Mobilize fires when cast: 90.2%

#### Statistical-ceiling-vs-spec catch (calibration discipline)

Original Phase 2 spec said "Voice cast rate >50% (it's a 2-of, fairly
drawn)". Observed: 36.7%. **This is the statistical ceiling, not a
bug.** For a 2-of in 60 cards across T4-5-kill games (~11-12 cards
seen):

  P(see ≥1) = 1 - C(58, K) / C(60, K)
  K=11: ~0.34   K=12: ~0.36   K=14: ~0.42

Voice IS being cast as often as the deck composition + game length
permit. Future spec authors: **sanity-check copy-frequency targets
against deck composition + expected game length before setting them
as pass criteria.** Round-number targets like ">50%" are the spec
equivalent of a magic constant. Always derive from the math.

#### Drift triage

If pre/post canonical drift exceeds ±2% WR:
- First check: did `_compute_roles` skip any card the old logic relied
  on? Compare `self.haste_threats ∪ self.sac_outlets ∪ self.face_burn
  ∪ self.token_producers ∪ self.energy_sources` against the old
  hardcoded constants block. Anything in the old block that's NOT in
  any role bucket is a candidate gap.
- Second check: priority order. The old fill-curve loop used
  `min(cmc, name)` ordering. The new `creatures_by_cmc` matches that.
  But the new explicit priority for things like Ocelot/Guide-first-in-
  main_phase2 may differ from the old tuple — verify ordering.
- Third check: Phlage / Ajani / Ocelot / Guide handlers — did they
  get called the same number of times pre/post? Add cast-rate logging
  comparable to the Ranger-Captain smoke.

### Constraints (non-negotiable)

1. **SKIP `engine/oracle_parser.py`.** It's in the WIP zone (untracked,
   mid-development per the priority-queue/telemetry pipeline buildout).
   Pulling it in adds risk + ties this commit to in-flight work. Use
   raw `c.oracle_text.lower()` string matching instead. Plenty robust
   for these role buckets.

2. **PRESERVE the Phlage CMC=0 kludge** (`gs.mana_pool.can_pay("{1}{R}{W}", 3)`).
   Just gate it on `self.has_phlage` instead of always-on. Don't try to
   fix the underlying data bug as part of this refactor.

3. **`SPECIAL_MECHANICS` dict** is the registry for cards with unique
   mechanics: Phlage / Ajani / Ocelot / Guide / Arena of Glory /
   Bombardment / Pyromancer. Each entry maps to a `has_<flag>` plus
   handler method. **Don't try to reduce these to oracle patterns** —
   they have interactions (Cat-die transform, gained-life-this-turn
   check, exert-mana, GY-dependent escape) that text matching can't
   capture cleanly.

4. **Don't commit until canonical 1000-game validation passes the
   ±2% / ±0.2 turn drift bounds.** The BE APL is load-bearing for
   65.3%-FWR-validated matchup-suite work. Functional equivalence on
   the canonical list is the floor.

5. **Hardcoded name constants block at top of file** — keep as
   documentation comments for the canonical 75. Don't import them as
   module-level constants anymore (the turn loop doesn't reference
   them). Removing them entirely would lose the human-readable card
   list at the top of the file.

### Estimated time

- `_compute_roles` + `_ensure_roles` + SPECIAL_MECHANICS scaffolding:
  ~45 min
- Refactor `main_phase` / `main_phase2` / `keep` / `bottom`: ~60-90 min
- Move per-card logic into handler methods (Phlage, Ajani, Ocelot,
  Guide, Arena, Bombardment, Pyromancer): ~60 min
- Pre-refactor baseline run (1000 games): ~5 min
- Post-refactor canonical validation (1000 games): ~5 min
- Variant stress test: write deck file + 1000 games + cast-rate
  monkey-patch trace: ~30 min
- Debug any drift: ~30-60 min budget

**Total: 3.5-4.5 hours, including validation and likely-needed
debugging round.**

### Risks

1. **`keep()` early-call problem.** `_compute_roles` needs the deck,
   but `keep()` runs before GameState is alive. Phase 1 punts via
   option (a) — defer role compute to first `main_phase`. This means
   `keep()` loses the role-aware on-the-play heuristic. If validation
   shows mulligan rate or kept-hand quality regressed, may need
   option (b) — restructure `base_apl.run_game` to construct
   GameState earlier. Out of Phase 1 scope; flag and fall back if
   hit.

2. **Oracle-text false positives.** Patterns use definite mechanical
   phrases (`"damage to any target"`, `"sacrifice a creature"`,
   `"create a"` + `"token"`). These don't appear in flavor text on
   tournament-legal cards. But cards with unusual oracle phrasing
   (split cards, modal spells, sagas) may not match cleanly — manual
   inspection of which cards land in which bucket post-refactor is
   part of validation.

3. **Special-mechanic interactions.** Some BE synergies emerge from
   card interactions (Guide of Souls triggers when an Ocelot Pride
   token enters). These work today because the trigger fires on
   EVERY creature ETB, not only on named cards. They should still
   work post-refactor because the new code only changes WHICH cards
   to cast, not WHAT happens when they ETB. **Verify in smoke test** —
   if Guide energy / life count diverges from canonical run, the
   trigger plumbing was perturbed.

4. **Phase 2 (variant lock-in registry) and Phase 3 (pure
   role-driven turn loop) are explicitly out of scope.** Phase 1
   captures 95% of the variant-adaptability value; Phase 2/3 can
   land later if Phase 1 proves out.

5. **Don't refactor other APLs in the same commit.** This pattern
   generalizes to IzzetProwess / AmuletTitan / Humans / etc. but the
   first instance is the proof point. Land BE alone, then iterate.

### Pre-refactor checklist (do these first)

1. Re-baseline BE goldfish per `mtg-sim/TODO.md` Small items
   (1000-game canonical run, update `ARCHITECTURE.md:117` with new
   number + date). The current cited T4.92 is stale; without a fresh
   baseline, post-refactor drift can't be measured cleanly.
2. Confirm `apl/aggro_base.py:AggroAPL` pattern is actually being
   used by some subclass (grep for `AggroAPL`). If yes, mirror its
   hook-method names. If no, the pattern is unproven and Phase 1
   becomes the first real consumer.
3. Read `apl/base_apl.py` `run_game` to understand exact GameState
   construction order — confirms whether option (a) defer-to-main_phase
   is necessary or option (b) restructure-base_apl is feasible.

## When to apply this pattern

A hand-tuned APL is a candidate for role-refactor when **all three** are true:

1. **Hardcoded card-name constants block** at top of the file
   (`RAGAVAN = "Ragavan, Nimble Pilferer"`, `OCELOT_PRIDE = "..."`, etc.).
   The constants block is the smell — it's the author's local registry
   of "things this turn loop knows about by name."

2. **Name-keyed iteration** in the turn loop:
   - `for name in (CARD_A, CARD_B):` haste loops
   - `if card.name == SPECIFIC_NAME:` deployment checks
   - Explicit priority tuples like `priority = (CARD1, CARD2, CARD3)`

3. **Variant adaptability matters** — the deck shell sees experimental
   builds (post-rotation, post-PT meta shifts, sideboard-vs-mainboard
   swaps, alternate cuts).

### Candidate APLs (verified 2026-04-25)

| APL | Hardcoded constants | Variant churn | Priority |
|---|---|---|---|
| `BorosEnergyAPL` | DONE (Phase 1+2 reference impl) | High (post-PT, RCQ season) | DONE |
| `IzzetProwessAPL` | YES (`SLICKSHOT`, `CORI_STEEL`, `DRC`, etc.) | High (Cori-Steel meta is volatile) | **next** |
| `AmuletTitanAPL` | YES (combo-engine constants) | Low-med (combo lists stable) | medium |
| `HumansAPL` | YES (tribal shell, post-Champion-of-the-Parish era) | Med | medium |
| `ModernDomainZooAPL` | YES (split between domain types) | Med-high | medium |
| `BorosEnergyMatchAPL` | YES (mirrors BorosEnergyAPL constants) | High (paired with BE) | high (after IzzetProwess) |

### Skip the pattern when

- APL is a `GenericAPL` stub (already deck-driven, no constants block to refactor).
- APL is a tightly-scripted combo deck where every card is essential to
  the line (Amulet Titan partly fits this — Phase 1 detection works
  for the support shell, but the combo line stays name-keyed by necessity).
- APL has no variant churn (Legacy Humans is more meta-stable than
  Modern Humans, e.g.).

### Execution checklist (use this when applying to next APL)

1. **Read current APL** in full. Identify the constants block,
   name-keyed loops, and per-card simulation methods (`_simulate_<card>_etb`, etc.).
2. **Pre-refactor 1000-game baseline** — ALWAYS do this first. Without
   a clean comparison number, post-refactor drift can't be measured.
   Update `ARCHITECTURE.md` if there's a stale baseline cited.
3. **Five-stage execution** following BE template:
   - Stage 1: re-baseline + commit
   - Stage 2: scaffolding (no behavior change) + commit + 100-game smoke
   - Stage 3: keep() + bottom() refactor + commit + 100-game smoke
   - Stage 4: main_phase refactor + commit + 100-game smoke
   - Stage 5: main_phase2 + handler extraction + commit + 1000-game smoke
   - Stage 6: variant stress test deck + commit
   - Stage 7: final 1000-game canonical validation
4. **Phase 2 if variant adaptability needs new combat/end-phase mechanics:**
   - Stage 1: dict simplification + dispatch helper + deck_names
   - Stage 2: new handler(s)
   - Stage 3: validation
5. **Architectural choice (mandatory):** keep individual handler call
   positions in main_phase / main_phase2; use unified dispatch ONLY
   for new combat/end phases. See "Architectural choice" section above.

## Changelog

- 2026-04-25 day: Created as forward-looking spec — source: 2026-04-25
  architectural-discussion thread. Execution originally deferred to a
  fresh session per context-fatigue concern.
- 2026-04-25 night: **Phase 1 (stages 1-7) and Phase 2 (stages 1-3)
  shipped on BorosEnergyAPL.** Commits 9de316f (re-baseline) → 4d3ef7b
  (scaffolding) → a4cfe3b (keep) → 9b9f515 (main_phase) → b5e6bb9
  (main_phase2) → 7dcdbbd (variant deck) → 66a23a8 (Phase 2 dict
  simplification) → 81470f8 (Voice Mobilize). Doc updated with actual
  results, architectural-choice section (individual call positions
  vs unified dispatch — the most important lesson), variant test
  observed numbers, statistical-ceiling-vs-spec calibration note,
  and "When to apply this pattern" section listing candidate APLs.
  Doc is now the template for IzzetProwess (next).
