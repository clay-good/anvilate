"""Random vibration from a declared spectrum, anchored to GSFC-STD-7000B's own overall levels.

GEVS Tables 2.4-3 and 2.4-4 state each spectrum by breakpoints and slopes and print its
overall level; integrating the log-log segments must give those levels back. Each table
gives its end levels rounded (0.026 g²/Hz for +6 dB/oct from 50 Hz down to 20 Hz), so the
match is to the table's own rounding.
"""

from __future__ import annotations

from math import log, pi, sqrt

import pytest

from anvilate.analysis import miles_random_vibration_grms
from anvilate.analysis.random_vibration import (
    LoadCombinationRule,
    miles_response_grms,
    psd_level,
    psd_overall_grms,
    random_vibration_load,
)
from anvilate.refusal import RefusalError
from anvilate.units import Quantity


def _spectrum(*points: tuple[float, float]) -> dict[str, list[Quantity]]:
    return {
        "frequencies": [Quantity(magnitude=f, unit="Hz") for f, _ in points],
        "asd": [Quantity(magnitude=a, unit="1/Hz") for _, a in points],
    }


_QUAL = _spectrum((20, 0.026), (50, 0.16), (800, 0.16), (2000, 0.026))
_ACCEPT = _spectrum((20, 0.013), (50, 0.08), (800, 0.08), (2000, 0.013))
_WORKMANSHIP = _spectrum((20, 0.01), (80, 0.04), (500, 0.04), (2000, 0.01))
_HEAVY_WORKMANSHIP = _spectrum((20, 0.01), (2000, 0.01))


@pytest.mark.parametrize(
    ("spectrum", "printed"),
    [(_QUAL, 14.1), (_ACCEPT, 10.0), (_WORKMANSHIP, 6.8), (_HEAVY_WORKMANSHIP, 4.4)],
    ids=["2.4-3 qualification", "2.4-3 acceptance", "2.4-4 workmanship", "2.4-4 over 182 kg"],
)
def test_the_gevs_overall_levels(spectrum, printed):
    assert psd_overall_grms(**spectrum) == pytest.approx(printed, abs=0.05)


def test_a_flat_spectrum_is_level_times_bandwidth():
    # 0.01 x (2000 - 20) = 19.8 g² -> 4.4497 Grms, exactly, with no slope involved
    assert psd_overall_grms(**_HEAVY_WORKMANSHIP) == pytest.approx(sqrt(19.8), rel=1e-12)


def test_a_minus_3_db_per_octave_segment_uses_the_logarithm():
    # a = 1/f is the n = -1 case: area = a1 f1 ln(f2/f1) = 0.04 x 500 x ln 4
    grms = psd_overall_grms(**_spectrum((500, 0.04), (2000, 0.01)))
    assert grms == pytest.approx(sqrt(0.04 * 500 * 2 * 0.6931471805599453), rel=1e-12)


def test_linear_integration_would_overstate_the_slopes():
    """The trapezoid under the straight-on-a-plot line is not the spectrum's area."""
    trapezoid = (0.026 + 0.16) / 2 * 30 + 0.16 * 750 + (0.16 + 0.026) / 2 * 1200
    assert psd_overall_grms(**_QUAL) < sqrt(trapezoid) - 1.0


def test_the_level_between_breakpoints_is_interpolated_log_log():
    # The table's rounded ends make the slope n = ln(0.16/0.026)/ln(2.5), close to +6 dB/oct
    level = psd_level(**_QUAL, at=Quantity(magnitude=40.0, unit="Hz"))
    slope = log(0.16 / 0.026) / log(50 / 20)
    assert level.to("1/Hz").magnitude == pytest.approx(0.026 * 2**slope, rel=1e-12)
    assert psd_level(**_QUAL, at=Quantity(magnitude=100.0, unit="Hz")).magnitude == 0.16


def test_a_100_hz_box_with_q_of_10_on_the_qualification_profile():
    load = random_vibration_load(
        **_QUAL,
        natural_frequency=Quantity(magnitude=100.0, unit="Hz"),
        quality_factor=10.0,
    )
    # By hand: √(π/2 · 100 · 10 · 0.16) = √251.33 = 15.85 Grms; 3σ = 47.56 g
    assert load.input_grms == pytest.approx(14.14, abs=0.005)
    assert load.asd_at_natural_frequency == pytest.approx(0.16, rel=1e-12)
    assert load.response_grms == pytest.approx(sqrt(pi / 2 * 100 * 10 * 0.16), rel=1e-12)
    assert load.peak_3_sigma == pytest.approx(3 * load.response_grms, rel=1e-12)
    assert load.design_load == load.peak_3_sigma  # no quasi-static
    assert load.assumption.startswith("Miles' equation assumes a single-degree-of-freedom")
    assert "single-degree-of-freedom" in str(load)


@pytest.mark.parametrize(
    ("rule", "expected"),
    [(LoadCombinationRule.ROOT_SUM_SQUARE, 50.0), (LoadCombinationRule.ABSOLUTE_SUM, 54.0)],
)
def test_the_declared_rule_combines_the_peak_with_quasi_static(rule, expected):
    # Pick f_n so that 3σ is exactly 40 g: Grms = 40/3, ASD = 0.16 -> f_n Q = (40/3)²/(π/2 · 0.16)
    fn_q = (40 / 3) ** 2 / (pi / 2 * 0.16)
    load = random_vibration_load(
        **_QUAL,
        natural_frequency=Quantity(magnitude=fn_q / 10, unit="Hz"),
        quality_factor=10.0,
        quasi_static=-14.0 if rule is LoadCombinationRule.ABSOLUTE_SUM else 30.0,
        rule=rule,
    )
    assert load.peak_3_sigma == pytest.approx(40.0, rel=1e-12)
    assert load.design_load == pytest.approx(expected, rel=1e-12)


def test_the_optomechanics_copy_is_the_same_implementation():
    flat = miles_random_vibration_grms(
        natural_frequency=Quantity(magnitude=250.0, unit="Hz"),
        quality_factor=15.0,
        input_asd=Quantity(magnitude=0.04, unit="1/Hz"),
    )
    assert flat == miles_response_grms(natural_frequency=250.0, quality_factor=15.0, asd=0.04)


# --- refusals -------------------------------------------------------------------------------


def test_a_natural_frequency_outside_the_spectrum_is_refused():
    with pytest.raises(RefusalError, match="outside the declared spectrum"):
        random_vibration_load(**_QUAL, natural_frequency=Quantity(magnitude=10.0, unit="Hz"),
                              quality_factor=10.0)  # fmt: skip


def test_breakpoints_must_rise():
    with pytest.raises(RefusalError, match="increasing frequency"):
        psd_overall_grms(**_spectrum((20, 0.01), (20, 0.02)))


@pytest.mark.parametrize("bad", [(0.0, 0.01), (20.0, 0.0), (20.0, -0.01)])
def test_a_log_log_breakpoint_is_positive(bad):
    with pytest.raises(RefusalError, match="positive"):
        psd_overall_grms(**_spectrum(bad, (2000, 0.01)))


@pytest.mark.parametrize("value", [float("nan"), float("inf")])
def test_a_non_finite_level_is_refused(value):
    with pytest.raises(ValueError):
        psd_overall_grms(**_spectrum((20, value), (2000, 0.01)))


def test_one_breakpoint_is_not_a_spectrum():
    with pytest.raises(RefusalError, match="at least two"):
        psd_overall_grms(**_spectrum((20, 0.01)))


def test_a_wrong_dimension_is_refused_by_name():
    with pytest.raises(RefusalError, match=r"asd\[0\]"):
        psd_overall_grms(frequencies=[Quantity(magnitude=20, unit="Hz")] * 2,
                         asd=[Quantity(magnitude=1, unit="m")] * 2)  # fmt: skip


@pytest.mark.parametrize("q", [0.5, 0.0, float("nan")])
def test_q_must_describe_a_resonance(q):
    with pytest.raises(ValueError, match="quality_factor"):
        miles_response_grms(natural_frequency=100.0, quality_factor=q, asd=0.04)


def test_the_rule_must_be_declared_as_one():
    with pytest.raises(RefusalError, match="rule"):
        random_vibration_load(**_QUAL, natural_frequency=Quantity(magnitude=100.0, unit="Hz"),
                              quality_factor=10.0, rule="rss")  # type: ignore[arg-type]  # fmt: skip
