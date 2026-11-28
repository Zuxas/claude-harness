"""The optimizer must not call Monte-Carlo noise an improvement (#16).

Done-when:
- testing an unchanged APL as a 'patch' yields NEUTRAL in >=95% of trials;
- a lower-win-rate, faster-avg-kill patch is rejected.

paired_verdict is pure, so these drive it with synthetic paired samples.

Run: python agents/scripts/test_optimizer_verdict.py
"""
import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import apl_optimizer as ao


def test_exact_noop_is_neutral():
    # Common random numbers: an unchanged APL gives identical per-seed results.
    kills = [4.2, 4.1, 4.3, 4.0, 4.25, 4.15, 4.35, 4.05, 4.2, 4.1]
    assert ao.paired_verdict(kills, list(kills), 0.9, 0.9) == "neutral"


def test_noisy_noop_is_neutral_at_least_95_percent():
    rng = random.Random(42)
    base = [4.2] * 10
    neutral = 0
    trials = 400
    for _ in range(trials):
        # A behaviour-changing but net-zero patch: paired deltas are noise
        # around 0 (SD ~0.052, matching the measured run-to-run spread).
        patched = [4.2 - rng.gauss(0, 0.052) for _ in range(10)]
        if ao.paired_verdict(base, patched, 0.90, 0.90) == "neutral":
            neutral += 1
    rate = neutral / trials
    assert rate >= 0.95, f"no-op neutral rate {rate:.3f} < 0.95"


def test_real_improvement_is_improved():
    base = [5.0] * 10
    patched = [4.6, 4.7, 4.65, 4.6, 4.7, 4.68, 4.62, 4.66, 4.64, 4.69]  # ~0.35 faster, tight
    assert ao.paired_verdict(base, patched, 0.90, 0.90) == "improved"


def test_lower_winrate_faster_kill_is_rejected():
    # Faster avg kill (over wins only) but the win rate dropped -> never improved.
    base = [5.0] * 10
    patched = [4.4] * 10          # clearly faster
    assert ao.paired_verdict(base, patched, 0.90, 0.84) == "worse"


def test_tiny_winrate_noise_does_not_block_a_real_gain():
    base = [5.0] * 10
    patched = [4.6] * 10
    # WR down 0.5pp (within the 1pp tolerance) must not veto a real improvement.
    assert ao.paired_verdict(base, patched, 0.90, 0.895) == "improved"


def test_mean_kill_ignores_none():
    assert ao._mean_kill([4.0, None, 6.0]) == 5.0
    assert ao._mean_kill([None, None]) is None


def test_wr_guard_vetoes_significant_sub_1pp_drop():
    # A real kill gain, with a CONSISTENT 0.4pp per-seed WR drop (below the 1pp
    # floor). With no series (legacy) it passes as IMPROVED; with the paired
    # per-seed WRs the consistent drop is significant and is vetoed as WORSE.
    base = [5.0] * 10
    patched = [4.6] * 10
    assert ao.paired_verdict(base, patched, 0.90, 0.896) == "improved"
    assert ao.paired_verdict(base, patched, 0.900, 0.896,
                             base_wr_series=[0.90] * 10,
                             patched_wr_series=[0.896] * 10) == "worse"


def test_wr_guard_noisy_sub_1pp_drop_not_vetoed():
    # Same tiny mean drop but high per-seed variance -> not significant -> the
    # kill gain stands.
    base = [5.0] * 10
    patched = [4.6] * 10
    bser = [0.90] * 10
    pser = [0.896 + (0.05 if i % 2 else -0.05) for i in range(10)]  # mean 0.896, noisy
    assert ao.paired_verdict(base, patched, 0.900, 0.896,
                             base_wr_series=bser, patched_wr_series=pser) == "improved"


def test_wr_guard_1pp_hard_veto_survives_noise():
    # A >1pp overall drop is vetoed by the hard floor regardless of the series.
    base = [5.0] * 10
    patched = [4.4] * 10
    assert ao.paired_verdict(base, patched, 0.90, 0.88,
                             base_wr_series=[0.90] * 10,
                             patched_wr_series=[0.88] * 10) == "worse"


def test_wr_regressed_paired_helper():
    base = [0.90] * 10
    assert ao._wr_regressed(0.90, 0.896, base, [0.896] * 10) is True     # consistent small drop
    assert ao._wr_regressed(0.90, 0.905, base, [0.905] * 10) is False    # WR went UP
    noisy = [0.896 + (0.05 if i % 2 else -0.05) for i in range(10)]
    assert ao._wr_regressed(0.90, 0.896, base, noisy) is False           # noisy -> not significant


def test_selection_prefers_higher_winrate_over_faster_kill():
    # A higher-WR patch beats a faster-kill one (WR primary, #37)...
    assert ao._selection_key(0.91, 0.10) > ao._selection_key(0.90, 0.50)
    # ...and among WR-neutral (same 1pp bucket) patches, faster kill wins.
    assert ao._selection_key(0.903, 0.50) > ao._selection_key(0.898, 0.30)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"  ok  {name}")
    print("test_optimizer_verdict: OK")
