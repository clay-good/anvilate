"""Uncertainty-aware margins: Monte Carlo propagation, sensitivity, determinism."""

from __future__ import annotations

from math import sqrt
from statistics import NormalDist

import pytest
from pydantic import ValidationError

from anvilate.uncertainty import (
    MarginUncertainty,
    Normal,
    Sensitivity,
    Symmetric,
    Uniform,
    sample_margin,
)

# -- distribution vocabulary ---------------------------------------------------


def test_normal_rejects_negative_std():
    with pytest.raises(ValueError, match="std must be non-negative"):
        Normal(mean=1.0, std=-0.1)


def test_uniform_mean_and_std_match_the_closed_form():
    u = Uniform(low=2.0, high=8.0)
    assert u.mean == pytest.approx(5.0)
    assert u.std == pytest.approx(6.0 / sqrt(12.0))


def test_uniform_rejects_reversed_bounds():
    with pytest.raises(ValueError, match="must not exceed high"):
        Uniform(low=9.0, high=1.0)


def test_symmetric_reads_half_width_as_three_sigma_by_default():
    s = Symmetric(nominal=100.0, half_width=6.0)
    assert s.mean == 100.0
    assert s.std == pytest.approx(2.0)  # 6 / 3σ
    flat = Symmetric(nominal=100.0, half_width=6.0, distribution="uniform")
    assert flat.std == pytest.approx(6.0 / sqrt(3.0))


def test_zero_spread_inputs_sample_their_center():
    import random

    rng = random.Random(0)
    assert Normal(mean=4.0, std=0.0).sample(rng) == 4.0
    assert Symmetric(nominal=7.0, half_width=0.0).sample(rng) == 7.0
    assert Uniform(low=3.0, high=3.0).sample(rng) == 3.0


# -- Monte Carlo propagation ---------------------------------------------------


def _linear(values):
    # f = 2*a - b: a linear response with a known closed-form distribution.
    return 2.0 * values["a"] - values["b"]


def test_linear_normal_inputs_match_closed_form_propagation():
    # a ~ N(10, 1), b ~ N(5, 0.5): f = 2a - b ~ N(15, sqrt(4 + 0.25)).
    inputs = {"a": Normal(mean=10.0, std=1.0), "b": Normal(mean=5.0, std=0.5)}
    result = sample_margin(_linear, inputs, required=12.0, seed=7, samples=40000)

    exact = NormalDist(15.0, sqrt(4.0 + 0.25))
    assert result.mean == pytest.approx(exact.mean, abs=0.05)
    assert result.std == pytest.approx(exact.stdev, abs=0.05)
    # Shortfall P(f < 12) matches the normal CDF within Monte Carlo error.
    assert result.shortfall_probability == pytest.approx(exact.cdf(12.0), abs=0.01)


def test_percentile_band_brackets_the_central_coverage():
    inputs = {"a": Normal(mean=10.0, std=1.0), "b": Normal(mean=5.0, std=0.5)}
    result = sample_margin(_linear, inputs, required=12.0, seed=7, samples=40000, coverage=0.90)
    exact = NormalDist(15.0, sqrt(4.25))
    assert result.lower == pytest.approx(exact.inv_cdf(0.05), abs=0.1)
    assert result.upper == pytest.approx(exact.inv_cdf(0.95), abs=0.1)
    assert result.lower < result.mean < result.upper


def test_first_order_sensitivity_shares_match_the_linear_weights():
    # For f = 2a - b, variance contributions are (2*σ_a)^2 = 4 and (σ_b)^2 = 0.25;
    # a drives 4/4.25 = 94.1% of the variance, b the rest.
    inputs = {"a": Normal(mean=10.0, std=1.0), "b": Normal(mean=5.0, std=0.5)}
    result = sample_margin(_linear, inputs, required=12.0, seed=7, samples=2000)
    assert [s.name for s in result.sensitivities] == ["a", "b"]  # ranked, largest first
    assert result.sensitivities[0].variance_share == pytest.approx(4.0 / 4.25, abs=1e-9)
    assert result.sensitivities[1].variance_share == pytest.approx(0.25 / 4.25, abs=1e-9)
    assert result.dominant().name == "a"


# -- determinism ---------------------------------------------------------------


def test_identical_seed_gives_identical_statistics():
    inputs = {"a": Normal(mean=10.0, std=1.0), "b": Normal(mean=5.0, std=0.5)}
    first = sample_margin(_linear, inputs, required=12.0, seed=42, samples=5000)
    second = sample_margin(_linear, inputs, required=12.0, seed=42, samples=5000)
    assert first == second


def test_result_is_independent_of_input_mapping_order():
    # Names are drawn in sorted order, so a differently-built mapping is identical.
    forward = {"a": Normal(mean=10.0, std=1.0), "b": Normal(mean=5.0, std=0.5)}
    reversed_ = {"b": Normal(mean=5.0, std=0.5), "a": Normal(mean=10.0, std=1.0)}
    assert sample_margin(_linear, forward, required=12.0, seed=3, samples=5000) == sample_margin(
        _linear, reversed_, required=12.0, seed=3, samples=5000
    )


def test_different_seed_shifts_the_estimate_slightly():
    inputs = {"a": Normal(mean=10.0, std=1.0), "b": Normal(mean=5.0, std=0.5)}
    a = sample_margin(_linear, inputs, required=12.0, seed=1, samples=5000)
    b = sample_margin(_linear, inputs, required=12.0, seed=2, samples=5000)
    assert a.mean != b.mean  # different draws
    assert a.mean == pytest.approx(b.mean, abs=0.1)  # but converging on the same truth


# -- fragility warning and guards ----------------------------------------------


def test_is_fragile_flags_a_material_shortfall_probability():
    # A nominal pass (SF 1.5 on the mean load) that a wide load scatter drags below
    # 1.0 often: P(load > 150) = 1 - Φ(50/40) ≈ 10.6%.
    inputs = {"load": Normal(mean=100.0, std=40.0)}
    # SF = capacity / load, capacity fixed at 150.
    result = sample_margin(
        lambda v: 150.0 / v["load"], inputs, required=1.0, seed=11, samples=20000
    )
    assert result.mean > 1.0  # nominally passing on the mean load
    assert result.shortfall_probability == pytest.approx(0.106, abs=0.02)
    assert result.is_fragile(threshold=0.05)  # yet fails materially often
    assert not result.is_fragile(threshold=0.9)  # not above a 90% bar


def test_sample_margin_guards_bad_arguments():
    inputs = {"a": Normal(mean=1.0, std=0.1)}
    with pytest.raises(ValueError, match="at least 2 samples"):
        sample_margin(lambda v: v["a"], inputs, required=1.0, seed=0, samples=1)
    with pytest.raises(ValueError, match="coverage must be between"):
        sample_margin(lambda v: v["a"], inputs, required=1.0, seed=0, coverage=1.0)
    with pytest.raises(ValueError, match="at least one input"):
        sample_margin(lambda v: 1.0, {}, required=1.0, seed=0)


def test_margin_uncertainty_is_frozen_and_renders():
    result = MarginUncertainty(
        samples=100,
        seed=0,
        required=1.5,
        mean=2.0,
        std=0.3,
        shortfall_probability=0.04,
        lower=1.6,
        upper=2.5,
        coverage=0.9,
        sensitivities=(Sensitivity(name="load", variance_share=1.0),),
    )
    assert "P(below 1.50) = 4.0%" in str(result)
    assert result.dominant().name == "load"
    with pytest.raises(ValidationError):
        result.mean = 3.0  # frozen
