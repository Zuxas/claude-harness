---
title: "External Eval — ML Win-Prob Calibration + ModernBERT Archetype Classifier"
domain: tech
type: ext-eval
date: 2026-06-26
status: research-spec (read-only; no code changed)
topic: win-probability calibration curve + reliability check; ModernBERT end-to-end fine-tune
repos_evaluated:
  - ratloop/MatchOutcomeAI        # MIT — VERIFIED, see correction
  - philschmid/deep-learning-pytorch-huggingface  # MIT (fine-tune-modern-bert notebook)
  - argilla-io/synthetic-data-generator           # Apache-2.0
our_files_touched_by_plan:
  - mtg-sim/ml/win_prob_model.py
  - mtg-sim/engine/race.py
  - mtg-sim/engine/bo3_match.py
  - mtg-meta-analyzer/gui/tabs/calibration.py
  - mtg-meta-analyzer/analysis/knn_classifier.py
  - mtg-meta-analyzer/analysis/card_embeddings.py (read-only ref)
  - mtg-meta-analyzer/analysis/modernbert_finetune.py (NEW, proposed)
---

# External Eval — ML Calibration + Classifier Improvement (2026-06-26)

READ-ONLY research + spec. No source code, git, or engine touched. This doc is the
only artifact written. All claims below are grounded in (a) the actual repo files
fetched from GitHub on 2026-06-26 and (b) our own source read this session.

---

## 0. License + audit correction (READ FIRST — corrects thingstolookinto.md)

| Repo | Real license (verified) | Use posture |
|---|---|---|
| `ratloop/MatchOutcomeAI` | **MIT** (`LICENSE`, 1060 bytes, verified via git tree) | Idea reference only — see below |
| `philschmid/deep-learning-pytorch-huggingface` | **MIT** (per repo) | Adapt notebook pattern w/ credit |
| `argilla-io/synthetic-data-generator` | **Apache-2.0** (per prior audit; keep NOTICE) | Adapt pattern w/ credit |
| `scikit-learn` (the *actual* calibration tooling) | **BSD-3-Clause**, already a dep | Plain library usage, no attribution debt |

**CORRECTION to `thingstolookinto.md` (lines 31-32 and 202):** the audit claims
ratloop "includes calibration curve analysis / CalibratedClassifierCV, binned
quantile analysis." **This is FALSE.** I fetched the repo's full git tree, README,
and the two most-likely notebooks (`model_comparison/gradient_boosting.ipynb`,
`model_comparison/model_evaluation.ipynb`) and quoted their sklearn imports. There
is **no** `calibration_curve`, **no** `CalibratedClassifierCV`, **no**
`brier_score_loss`, and **no** reliability diagram anywhere in the 9 notebooks.
ratloop's only metrics are accuracy / precision / recall / F1 + a confusion-matrix
heatmap. Its "calibration" is purely informal: the author picked GradientBoosting
over XGBoost because its `predict_proba()` outputs *looked* closer to bookmaker
odds ("more realistic probabilities, which closely matched the odds given by major
bookmakers").

**Consequence:** the reliability technique we want is **scikit-learn's**
(`sklearn.calibration.calibration_curve` + `CalibratedClassifierCV` + BSD-3), not
ratloop's. Calling those functions is plain usage of a dependency we already ship —
there is **no code adaptation from ratloop and therefore no MIT-attribution
obligation** to it. What ratloop legitimately contributes is the *idea*: validate a
model's predicted probabilities against an external ground truth (bookmaker odds for
them; real melee.gg matchup WR for us). Credit ratloop for that idea in a one-line
comment; cite scikit-learn for the method. Suggested fix to the audit: change "includes
calibration curve analysis" to "demonstrates the *idea* of validating probabilities
against external odds; the sklearn calibration tooling is ours to add, not theirs."

---

## 1. Two calibration objects — DO NOT conflate

The word "calibration" maps to two *different* statistical objects in our stack.
Every plan below states which one it is, because the metric differs.

**Object A — per-game reliability (true calibration curve).**
Pairs = `(predicted_win_prob, did_win_binary)` over many individual games.
Question: "When the model says 70%, does it win ~70% of the time?"
Metrics: `calibration_curve`, Brier score, ECE. This is the textbook reliability
diagram and applies wherever we emit a per-game probability from a fitted classifier.
**Home: `mtg-sim/ml/win_prob_model.py`.**

**Object B — aggregate-rate agreement (sim-vs-real matchup matrix).**
Pairs = `(sim_matchup_WR, real_matchup_WR, n_real_matches)` over archetype pairs.
Each point is an *aggregate rate*, not a binary outcome. Question: "Does our sim's
predicted matchup % track the real-world matchup %?"
Metrics: weighted scatter vs y=x, fitted slope/intercept, sample-weighted mean
abs error. **Brier / per-game `calibration_curve` DO NOT apply here** (you don't
have per-game outcomes, you have two rates). **Home:
`mtg-meta-analyzer/gui/tabs/calibration.py`** (already collects exactly these triples).

> Pitfall the FWR side hides: `engine/bo3_match.py::match_wr_a()` and
> `engine/race.py::race_win_probability()` produce *aggregate* win % over N matches,
> not per-match probabilities. They are Object-B quantities. Do not feed an FWR
> number into a per-game Brier — it is a category error.

---

## 2. OUR current state (grounded read)

### mtg-sim (win-prob / FWR)
- **`ml/win_prob_model.py`** — GBM (default) per-turn win-prob classifier.
  - Line ~142 already does `from sklearn.calibration import CalibratedClassifierCV`
    **but never uses it** (dead import).
  - Lines ~178-182 already compute and print `brier_score_loss(yte, yprob)` and
    ROC-AUC. So Object-A metrics are *half-wired*: Brier is printed, but there is
    **no reliability curve, no ECE, and the model is never actually calibrated.**
  - `predict_proba()` output is consumed live by `predict_win_prob()` during APL
    decisions — i.e. uncalibrated probabilities are already steering sideboard/line
    choices. This is the trust gap the task names.
- **`engine/race.py`** — Monte-Carlo goldfish race → matchup win %. Object B.
- **`engine/bo3_match.py`** — `run_bo3_set` → `match_wr_a()` FWR. Object B.

### mtg-meta-analyzer (classifier + existing "calibration" tab)
- **`gui/tabs/calibration.py`** — MISNAMED. It is an Object-B sim%-vs-real% matchup
  *matrix* (color-coded by |sim-real| delta), not a reliability diagram. It already
  builds the exact `{sim_pct, real_pct, sample_size}` triples we need for a real
  Object-B calibration scatter — only the visualization is missing.
- **`analysis/knn_classifier.py`** — current archetype ML path: frozen ModernBERT
  *card* vectors (`analysis/card_embeddings.py`, 768-dim, 32k cards) pooled into a
  deck vector → `KNeighborsClassifier(metric="cosine")`. Confidence = fraction of
  k neighbors agreeing (`predict_proba().max()`). `hybrid_classify()` = signature
  rules first (`analysis/archetype_classifier.py`), KNN fallback.
- **`analysis/predictions.py`** — meta-trend self-validation. Logs binary
  correct/wrong only; no probability emitted, so no reliability curve to add here.
- **DB facts (queried this session, `data/mtg_meta.db`):** labeled decklists by
  format — Standard 37,539 / Modern 13,794 / Pioneer 8,054 / Legacy 6,340 /
  Pauper 3,927. Distinct archetypes: Standard 389, Modern 532, Legacy 539,
  Pauper 586, Pioneer 193. **610 (archetype,format) pairs have >=5 decks.** Head is
  fat, tail is very long (hundreds of <5-sample archetypes) — drives the synthetic
  layer in Plan 2.

---

## 3. DELIVERABLE 1 — Calibration curve + reliability check on win-prob / FWR

### 1A — Per-game reliability for the GBM win-prob model  [Value 5 / Effort S / Risk Low]
**Object A. This is the anchor — finishes wiring that is already half-present.**

OUR file: `mtg-sim/ml/win_prob_model.py` (function `train_model`, plus a small new
helper). No engine changes. matplotlib in **Agg** mode (headless; ASCII-only
terminal per CONVENTIONS).

Exact steps inside `train_model`, after `yprob = model.predict_proba(Xte)[:,1]`:

1. Reliability curve (the ratloop-idea, sklearn-method):
   ```python
   from sklearn.calibration import calibration_curve
   frac_pos, mean_pred = calibration_curve(
       yte, yprob, n_bins=10, strategy="quantile")   # quantile => equal-count bins
   ```
2. Hand-rolled ECE (sklearn has no ECE scalar):
   ```python
   import numpy as np
   def expected_calibration_error(y_true, y_prob, n_bins=10):
       bins = np.quantile(y_prob, np.linspace(0, 1, n_bins + 1))
       bins[0], bins[-1] = 0.0, 1.0
       idx = np.clip(np.digitize(y_prob, bins[1:-1]), 0, n_bins - 1)
       ece = 0.0
       for b in range(n_bins):
           m = idx == b
           if m.any():
               ece += m.mean() * abs(y_true[m].mean() - y_prob[m].mean())
       return float(ece)
   ece = expected_calibration_error(ya[...test...], yprob)   # use yte/yprob
   ```
3. Actually calibrate the model (use the dead import). Wrap the fitted GBM:
   ```python
   from sklearn.calibration import CalibratedClassifierCV
   # isotonic for >~1k samples (we have 100k+ snapshots), sigmoid if data is thin
   calib = CalibratedClassifierCV(model, method="isotonic", cv="prefit")
   calib.fit(Xcal, ycal)   # hold out a calibration split distinct from Xtr/Xte
   ```
   Report Brier + ECE **before vs after** calibration; persist whichever is lower as
   the live model (`save_model`). NOTE: split three ways (train / calibrate / test)
   so the reliability diagram is measured on data the calibrator never saw.
4. Plot to a PNG artifact (no GUI dependency):
   ```python
   import matplotlib; matplotlib.use("Agg")
   import matplotlib.pyplot as plt
   fig, ax = plt.subplots(figsize=(5,5))
   ax.plot([0,1],[0,1],"--",color="gray",label="perfect")
   ax.plot(mean_pred, frac_pos, "o-", label=f"GBM (Brier={brier:.3f}, ECE={ece:.3f})")
   ax.set_xlabel("Mean predicted win prob"); ax.set_ylabel("Observed win rate")
   ax.set_title("Win-prob reliability"); ax.legend()
   fig.savefig("data/win_prob_calibration.png", dpi=120, bbox_inches="tight")
   ```
5. Make `predict_win_prob()` load the calibrated model (same `data/` path).

Acceptance: `python -m ml.win_prob_model --train` prints Brier+ECE before/after and
writes `data/win_prob_calibration.png`; calibrated Brier <= raw Brier. Risk is low
because the import + Brier already exist; we are completing, not inventing.
Credit comment to add: `# reliability technique: scikit-learn calibration_curve
(BSD-3); idea of validating probs vs external truth: ratloop/MatchOutcomeAI (MIT)`.

### 1B — Aggregate sim-vs-real calibration plot in the existing tab  [Value 4 / Effort M / Risk Low]
**Object B. Reframe `gui/tabs/calibration.py`; do NOT build a second tab.**

OUR files: `mtg-meta-analyzer/gui/tabs/calibration.py` (+ existing
`gui/widgets/chart_canvas.py` for the matplotlib QtAgg canvas).

The worker already emits `{sim_pct, real_pct, sample_size}` per pair. Add an
aggregate calibration view alongside the matrix:
1. Collect all cells where `real_pct is not None` into arrays
   `x=sim_pct, y=real_pct, w=sample_size`.
2. Scatter on a `ChartCanvas`, point size ∝ `sample_size`, draw y=x diagonal.
3. Fit a sample-weighted line: `np.polyfit(x, y, 1, w=np.sqrt(w))`. Slope < 1 =
   sim over-confident at the extremes; intercept ≠ 0 = systematic bias.
4. Headline scalar = sample-weighted mean abs error
   `sum(w*|x-y|)/sum(w)` — the Object-B analogue of ECE.
5. Label it explicitly: "Aggregate matchup-rate calibration (NOT per-game Brier)."

Acceptance: tab shows scatter + diagonal + fitted slope + weighted MAE; numbers
reconcile with the matrix deltas already displayed. Effort is M only because it is
GUI/threading work, not new statistics.

### 1C — (Optional, later) FWR confidence bands  [Value 2 / Effort S / Risk Low]
`bo3_match.run_bo3_set` returns a point FWR. Add a Wilson interval on `a_wins/n`
(reuse `mtg-meta-analyzer/analysis/wilson.py` pattern) so a 68% FWR at N=200 is
reported as 68% ±~6.5pp. Prevents over-reading sim noise as a real edge. Not
calibration per se, but the same "trust the number" goal.

---

## 4. DELIVERABLE 2 — Fine-tune ModernBERT end-to-end on archetype labels

### Current vs proposed
- **Current:** frozen ModernBERT *card* embeddings → mean-pooled deck vector →
  cosine KNN (`analysis/knn_classifier.py`). The transformer is never trained on
  our task; only the neighbor lookup is "learned."
- **Proposed:** `AutoModelForSequenceClassification` on `answerdotai/ModernBERT-base`,
  input = the decklist rendered as text, label = archetype, trained with
  philschmid's recipe. End-to-end, task-specific.

### Plan  [Value 3 / Effort L / Risk Medium]
OUR files: new `analysis/modernbert_finetune.py`; new Layer-5 hook in
`knn_classifier.hybrid_classify`; artifact under `data/models/`.

1. **Dataset = labeled DECKLISTS, not match records.** Reuse the exact source
   `knn_classifier.build_training_set` already pulls: `decks` joined to
   `deck_cards`/`cards`, `archetype` non-null, mainboard only, format-scoped,
   `>=N` decks/archetype. **Do NOT use the "260k match records"** — those are W/L
   results feeding Glicko ratings, the wrong dataset for a text classifier (the
   prior audit's "260k match record dataset as training data" is mistaken here).
   Real sizing: Standard alone = 37,539 labeled decklists across the head
   archetypes; cap the label set to (archetype,format) pairs with >=5 (610 pairs
   total across formats) or a higher floor like >=20 for a clean head.
2. **Serialize each deck to text** (deterministic ordering so the tokenizer sees a
   stable string): e.g. `"4 Ragavan; 4 Mishra's Bauble; 2 Murktide Regent; ..."`,
   sorted by quantity then name, sideboard appended after a `[SB]` sentinel.
3. **philschmid recipe** (`fine-tune-modern-bert-in-2025.ipynb`, MIT):
   ```python
   from transformers import (AutoTokenizer, AutoModelForSequenceClassification,
                             TrainingArguments, Trainer)
   tok   = AutoTokenizer.from_pretrained("answerdotai/ModernBERT-base")
   model = AutoModelForSequenceClassification.from_pretrained(
               "answerdotai/ModernBERT-base", num_labels=n_archetypes)
   args  = TrainingArguments(per_device_train_batch_size=32, learning_rate=5e-5,
               num_train_epochs=5, eval_strategy="epoch", bf16=True,
               optim="adamw_torch_fused", output_dir="data/models/mbert_arch")
   # compute_metrics -> weighted F1 (sklearn). philschmid hit F1 0.993 in 321s on an L4.
   ```
4. **Eval gate vs the incumbent:** held-out F1 + a per-class confusion matrix
   **against the current KNN** on the same split. Promote into `hybrid_classify`
   as Layer 5 (after KNN) **only if it beats the KNN baseline**; otherwise keep KNN.

### Expected payoff (honest)
Signature-card rules (`archetype_classifier.py`) already resolve most mainstream
decks deterministically; the transformer only ever sees decks that fell through to
KNN. So end-to-end fine-tune improves the **fallback tail**, not the whole pipeline —
upside is real but bounded. The 91% headline accuracy is mostly carried by the rules
layer. Frame this as "lift the KNN-fallback floor on ambiguous/low-signal decks,"
not "push the whole classifier past 91%."

### Effort / Risk drivers
- **Hardware is the gate (Risk Medium).** philschmid used an L4 GPU (24GB). User is
  Windows 11 / Python 3.13, no GPU stated. CPU fine-tune of ModernBERT-base over
  ~30k decklists is slow (hours). Route training to Colab/cloud or the local Gemma
  box; ship only the inference artifact back to `data/models/`. Inference on CPU is
  fine (single forward pass per deck).
- **transformers/torch are heavy deps** not currently in `requirements.txt`. Keep
  the import lazy (mirror how `card_embeddings.is_available()` guards) so the GUI
  never hard-fails when torch is absent — fall back to KNN.

### Synthetic-data sub-plan (argilla, Apache-2.0)  [Value 2 / Effort M / Risk Medium]
Only justified for the long tail: hundreds of archetypes have <5-20 decks and will
be dropped from the label set above. For those, the argilla
`fine-tune-modernbert-classifier.ipynb` pattern (LLM-generate synthetic decklists in
the archetype's style → validate in Argilla → add as minority-class samples) can lift
rare-archetype recall. **Caution:** synthetic decklists risk hallucinated/illegal
cards — gate every generated list through `db.card_data` existence checks (the same
guard the puzzle authoring path already uses) before it enters training. Defer until
1A/1B and the base fine-tune are done.

---

## 5. Priority / sequencing

| # | Item | Object | Value | Effort | Risk | OUR file(s) |
|---|---|---|---|---|---|---|
| 1A | GBM reliability curve + ECE + actual CalibratedClassifierCV | A (per-game) | 5 | S | Low | `mtg-sim/ml/win_prob_model.py` |
| 1B | Sim-vs-real aggregate calibration plot (reframe tab) | B (rate) | 4 | M | Low | `mtg-meta-analyzer/gui/tabs/calibration.py` |
| 1C | FWR Wilson confidence bands | B (rate) | 2 | S | Low | `mtg-sim/engine/bo3_match.py` |
| 2  | ModernBERT end-to-end fine-tune (decklists → archetype) | n/a | 3 | L | Med | new `analysis/modernbert_finetune.py` + `knn_classifier.py` |
| 2b | Argilla synthetic data for <20-sample archetypes | n/a | 2 | M | Med | `analysis/modernbert_finetune.py` |

Do 1A first (highest value, smallest effort, completes existing half-wired code).

---

## Changelog
- 2026-06-26: Initial research spec. Verified all 3 external repos + licenses on
  GitHub. Corrected thingstolookinto.md's false "ratloop has calibration curve"
  claim (it has none). Read OUR win_prob_model.py, race.py, bo3_match.py,
  knn_classifier.py, archetype_classifier.py, predictions.py, calibration.py.
  Queried mtg_meta.db for real decklist/archetype counts.
