"""Sampling audit (CS2): injected-RNG sampler + Screen false-pass control chart."""
from __future__ import annotations

import random

from genesys.inspection.audit import FalsePassChart, should_audit


def test_sampler_is_deterministic_under_a_seeded_rng():
    # Same seed + same rate -> identical decision sequence (no Math.random nondeterminism).
    seq_a = [should_audit(random.Random(1234), rate=0.05) for _ in range(1)]
    seq_b = [should_audit(random.Random(1234), rate=0.05) for _ in range(1)]
    assert seq_a == seq_b


def test_rate_zero_never_audits_and_rate_one_always_audits():
    rng = random.Random(0)
    assert should_audit(rng, rate=0.0) is False
    assert should_audit(rng, rate=1.0) is True


def test_sampled_fraction_is_near_the_rate_over_many_draws():
    rng = random.Random(42)
    n = 10000
    hits = sum(should_audit(rng, rate=0.05) for _ in range(n))
    assert 0.03 * n < hits < 0.07 * n     # ~5%, stable under the fixed seed


def test_false_pass_chart_tracks_and_breaches():
    chart = FalsePassChart()
    for _ in range(10):
        chart.record_pass()
    assert chart.false_pass_rate() == 0.0
    assert chart.breached(0.10) is False
    chart.record_false_pass()             # one audit upheld -> Screen false pass
    chart.record_false_pass()
    assert chart.false_pass_rate() == 0.2
    assert chart.breached(0.10) is True


def test_chart_rate_is_zero_with_no_passes():
    assert FalsePassChart().false_pass_rate() == 0.0
    assert FalsePassChart().breached(0.10) is False
