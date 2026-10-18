"""Plastic retention after time at temperature, from a declared creep-modulus record.

A fixed deflection's force scales with the modulus (Roark), so the retained force is
F₀·E_c/E₀. Between record points the modulus is interpolated in log time; outside the
record's temperature or time range the check is not evaluated, never extrapolated.
"""

from __future__ import annotations

from math import log10

import pytest

from anvilate.analysis.plastic_retention import (
    CreepModulusPoint,
    CreepModulusRecord,
    retention_after_creep,
)
from anvilate.refusal import RefusalError
from anvilate.units import Quantity

_CURVE_85 = CreepModulusRecord(
    temperature=Quantity(magnitude=85.0, unit="degC"),
    points=tuple(
        CreepModulusPoint(hours=h, modulus=Quantity(magnitude=e, unit="MPa"))
        for h, e in ((1, 5_500), (10, 5_000), (100, 4_500), (1_000, 4_000), (10_000, 3_600))
    ),
    source="supplier creep data, PA66-GF30 conditioned, 85 °C (illustrative)",
)


def _retain(hours: float, temperature_c: float = 85.0):
    return retention_after_creep(
        initial_force=Quantity(magnitude=40.0, unit="N"),
        short_term_modulus=Quantity(magnitude=6_000.0, unit="MPa"),
        temperature=Quantity(magnitude=temperature_c, unit="degC"),
        hours=hours,
        records=[_CURVE_85],
    )


def test_a_clip_after_a_hot_summer():
    """The spec's scenario: a glass-filled clip, 1,000 hours at 85 °C."""
    result = _retain(1_000)
    assert result.creep_modulus == 4_000
    assert result.force == pytest.approx(40 * 4_000 / 6_000, rel=1e-12)  # 26.67 N
    assert result.fraction == pytest.approx(2 / 3, rel=1e-12)
    assert "supplier creep data" in str(result)


def test_between_points_the_modulus_is_interpolated_in_log_time():
    # 300 h: 4,500 + (4,000 − 4,500) × log(3)/log(10) = 4,261.44 MPa
    result = _retain(300)
    assert result.creep_modulus == pytest.approx(4_500 - 500 * log10(3), rel=1e-12)


def test_no_time_or_temperature_is_extrapolated():
    late = _retain(20_000)
    assert late.force is None and "outside the record's 1–10000 h" in late.reason
    hotter = _retain(1_000, temperature_c=105)
    assert hotter.force is None and "no creep-modulus record at 105 °C" in hotter.reason
    assert "not evaluated" in str(hotter)


def test_a_record_that_stiffens_is_refused():
    stiff = CreepModulusRecord(
        temperature=Quantity(magnitude=85.0, unit="degC"),
        points=(CreepModulusPoint(hours=1, modulus=Quantity(magnitude=7_000, unit="MPa")),),
        source="a typo",
    )
    with pytest.raises(RefusalError, match="does not stiffen"):
        retention_after_creep(initial_force=Quantity(magnitude=40.0, unit="N"),
                              short_term_modulus=Quantity(magnitude=6_000.0, unit="MPa"),
                              temperature=Quantity(magnitude=85.0, unit="degC"), hours=1,
                              records=[stiff])  # fmt: skip


@pytest.mark.parametrize("hours", [0.0, -5.0, float("nan")])
def test_hours_must_be_positive_and_finite(hours):
    with pytest.raises(ValueError, match="hours"):
        _retain(hours)
