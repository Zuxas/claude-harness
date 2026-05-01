---
title: LLM-as-judge APL evaluation — 30-question ground-truth test set + Gemma scoring
status: PROPOSED
created: 2026-04-30
updated: 2026-04-30
project: mtg-sim
estimated_time: 90-120 min
related_findings: harness/knowledge/tech/external-research-mtg-ai-2026-04-30.md
related_commits:
supersedes:
superseded_by:
---

# Spec: LLM-as-Judge APL Evaluation

## Goal

Build a question-answer test set and Gemma 12B judge that scores APL decision quality
independently of sim WR%. WR% validates that code runs — it cannot catch oracle-incorrect
or strategically-wrong decisions that happen to cancel out statistically. The LLM-as-judge
catches reasoning errors: "given this board state and oracle text, does the APL make the
correct decision?"

Inspired by the mtg-agents.com evaluation methodology (45-question test set, LLM-as-judge,
iterative judge prompt calibration). See `harness/knowledge/tech/external-research-mtg-ai-2026-04-30.md`.

## Pre-flight reads

1. `harness/knowledge/tech/external-research-mtg-ai-2026-04-30.md` — LLM-as-judge methodology
2. `harness/scripts/verify_oracle.py` — existing oracle verification for pattern reference
3. `harness/knowledge/tech/spec-authoring-lessons.md`
4. `harness/IMPERFECTIONS.md:no-llm-as-judge-apl-evaluation`

## Scope

### In scope
- Build `harness/scripts/apl_judge.py` — loads question set, runs each against target APL,
  calls Gemma 12B as judge, outputs per-question PASS/FAIL + summary score
- Build initial 30-question test set in `harness/data/apl_judge_questions.json`
- Three question types (10 each): oracle fidelity, strategic decisions, keep/mulligan
- Judge prompt calibration: verify judge agrees with human on 5 known-correct + 5 known-incorrect
- Score Boros Energy as the reference APL (should score >90% as the best-maintained APL)

### Explicitly out of scope
- Automated fix suggestions (oracle-verify handles code-level issues; this handles decision-level)
- Auto-commit based on scores
- Questions requiring engine simulation to answer (pure code inspection only)

## Question Set Design

### Type 1: Oracle fidelity (10 questions)

Format:
```json
{
  "type": "oracle_fidelity",
  "card": "Solitude",
  "oracle_text": "If you cast this spell, exile a white card from your hand rather than pay its mana cost. When Solitude enters the battlefield, exile target non-white creature an opponent controls. That creature's controller gains life equal to its power.",
  "question": "When Solitude is cast via evoke (exile a white card), does the APL correctly pay the white card from hand before casting?",
  "apl_grep_term": "Solitude",
  "expected": "PASS: APL should remove a white card from hand when evoking. FAIL: APL casts Solitude without removing a white card.",
  "target_apls": ["jeskai_blink_match.py", "goryos_match.py"]
}
```

Initial oracle fidelity questions (10):
1. Solitude evoke — white card removal from hand
2. Phlage ETB — sacrifice unless escaped
3. Lava Dart flashback — sacrifice a Mountain
4. Ephemerate — {W} mana payment
5. Goryo's Vengeance — "Until end of turn, it gains haste and 'At the beginning of the next end step, exile it.'"
6. Wrath of the Skies — X energy payment matches threat CMC
7. Consign to Memory — counter target triggered ability (not spell)
8. Phelia exile — end-step return trigger
9. Force of Will — exile a blue card from hand
10. Prismatic Ending — CONVERGE: X = number of colors of mana spent

### Type 2: Strategic decisions (10 questions)

Format:
```json
{
  "type": "strategic",
  "deck": "Izzet Prowess",
  "principle": "Playbook: Focus on Guide of Souls (1/2) — THE engine piece. Kill with Lava Dart or Unholy Heat.",
  "board_state": "Opponent has Guide of Souls (1/2) and Ajani (0/5) on board. We have Lava Dart in hand and 3 damage dealt. Should we kill Guide or cast Dart face for 1 damage?",
  "expected": "PASS: APL targets Guide of Souls with Dart during setup turns. FAIL: APL casts Dart face at opponent instead of killing Guide.",
  "target_apls": ["izzet_prowess_match.py"]
}
```

Initial strategic questions (10):
1. Izzet Prowess: kill Guide of Souls vs Bolt face
2. Boros Energy: attack vs hold back when behind on board
3. Jeskai Blink: tap out for threat vs hold up Ephemerate mana
4. Goryo's: Goryo's target priority (Griselda vs Emrakul)
5. Amulet Titan: sacrifice Amulet to Claws vs keep for bounce
6. Domain Zoo: attack with Scion before granting keywords vs after
7. Jeskai Blink: Wrath targets priority (kill their best creature vs clear board)
8. Boros Energy: Pyromancer activation priority (fill GY vs deal damage)
9. Izzet Prowess: hold Mutagenic Growth for combat vs cast for prowess
10. Boros Energy: Ocelot Pride city's blessing threshold check

### Type 3: Keep/mulligan (10 questions)

Format:
```json
{
  "type": "mulligan",
  "deck": "Boros Energy",
  "role": "aggro",
  "on_play": true,
  "hand": "Mountain, Sacred Foundry, Guide of Souls, Ajani Nacatl, Lightning Bolt, Phlage, Ranger-Captain",
  "expected": "KEEP: 2 lands, Guide (engine piece), Ajani (threat). Classic aggro keep per 2-1-2 rule.",
  "rationale": "Nettle 2-1-2: keep with 2 lands + 1 threat. This hand has 2 lands and 2 threats."
}
```

Initial mulligan questions (10):
- 3 hands: clear keep (2+ lands, 1+ threats)
- 3 hands: clear mulligan (0 lands, or 6 lands 1 spell)
- 4 hands: edge cases (2 lands + 0 threats: mulligan; 1 land + 3 threats: mulligan; etc.)

Use Nettle 2-1-2 as ground truth for aggro keeps.

## Implementation

### apl_judge.py

```python
"""
apl_judge.py -- LLM-as-judge APL decision quality scorer.

Loads the question set, greps the target APL for relevant code sections,
calls Gemma 12B with the judge prompt, outputs PASS/FAIL per question
and a summary score.

Usage:
    python harness/scripts/apl_judge.py --apl apl/jeskai_blink_match.py
    python harness/scripts/apl_judge.py --apl apl/boros_energy.py --category oracle_fidelity
    python harness/scripts/apl_judge.py --all-canonical
"""
```

Judge prompt template:
```
You are evaluating whether an MTG simulation APL (Action Priority List) makes correct decisions.

QUESTION TYPE: {type}
CARD/DECK: {card_or_deck}
ORACLE TEXT (if applicable): {oracle_text}
PRINCIPLE/BOARD STATE: {question}

RELEVANT APL CODE:
{grep_context}

EXPECTED BEHAVIOR: {expected}

Does the APL code implement the expected behavior?

Answer format:
RESULT: PASS | FAIL
REASON: [one sentence explaining why]
```

### Judge calibration (mandatory before scoring any APL)

Before running the full test set, verify the judge is calibrated:
1. Run 5 questions where the APL is known-correct (Boros Energy, confirmed via oracle-verify)
2. Run 5 questions where the APL is known-incorrect (Goryo's pre-fix Solitude bug)
3. Judge must agree with human on 9/10. If <9/10, adjust judge prompt and re-run.

### Scoring

```
APL score = correct_answers / total_questions_applicable_to_that_deck
Target: >85% for canonical APLs
Flag: <70% → add to cross-canonical-apl-shared-card-bug-pattern backlog
Reference: Boros Energy should score >90%
```

## Validation gates

| Gate | Acceptance | Stop trigger |
|---|---|---|
| 1 — judge calibration | Judge agrees 9/10 on calibration set | <9/10 — adjust prompt first |
| 2 — BE reference score | Boros Energy scores >85% | <85% — questions or judge wrong |
| 3 — question coverage | All 3 types represented | Any type missing from set |
| 4 — performance | Full 30-question run in <5 min on Gemma 12B | >10 min — optimize grep context |

## Stop conditions

- **Judge calibration fails** (<9/10 on calibration set): STOP. Adjust judge prompt. Do not score APLs with miscalibrated judge.
- **Boros Energy scores <70%**: STOP. Questions are wrong or judge is wrong. Investigate.

## Future work (NOT in scope)

- Grow question set to 50+ as new oracle bugs are discovered — each fixed bug becomes a new test question
- Per-session pre-commit hook that scores recently-touched APLs (only run questions relevant to changed cards)
- Cross-APL question propagation: if Solitude evoke is tested for Jeskai Blink, auto-generate same question for Goryo's

## Changelog

- 2026-04-30: Created (PROPOSED). Based on mtg-agents.com evaluation methodology.
  30-question design, 3 categories, Gemma 12B judge, Boros Energy as reference.
