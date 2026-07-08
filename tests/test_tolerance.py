"""Tests for tolerance management, tracking the tolerance-management spec."""

from __future__ import annotations

import pytest

from anvilate.tolerance import (
    AngularTolerance,
    GeneralTolerance,
    ToleranceClass,
    ToleranceRangeError,
    general_angular_tolerance,
    general_tolerance,
)
from anvilate.units import Quantity


def _mm(x: float) -> Quantity:
    return Quantity(magnitude=x, unit="mm")


def test_size_range_lookup_with_citation() -> None:
    # Scenario: size-range lookup — a 35 mm dimension under class m resolves to
    # the 30-120 mm range's ±0.3 mm with its ISO 2768-1 citation.
    g = general_tolerance(_mm(35), ToleranceClass.MEDIUM)
    assert isinstance(g, GeneralTolerance)
    assert g.deviation.to("mm").magnitude == pytest.approx(0.3)
    assert "30" in g.size_range and "120" in g.size_range
    assert "ISO 2768-1" in g.source


def test_default_class_is_medium() -> None:
    # Scenario: default class applied — omitting the class governs by medium.
    assert general_tolerance(_mm(35)).tolerance_class is ToleranceClass.MEDIUM


def test_range_boundary_is_inclusive_of_upper() -> None:
    # 30 mm belongs to the 6-30 range (±0.2), not the 30-120 range.
    g = general_tolerance(_mm(30), "m")
    assert g.deviation.to("mm").magnitude == pytest.approx(0.2)
    assert "up to 30 mm" in g.size_range


def test_class_parses_from_letter_or_word() -> None:
    # Bridges the Spec IR's free-form tolerance_class string.
    assert ToleranceClass.parse("m") is ToleranceClass.MEDIUM
    assert ToleranceClass.parse("medium") is ToleranceClass.MEDIUM
    assert ToleranceClass.parse("F") is ToleranceClass.FINE
    assert ToleranceClass.MEDIUM.letter == "m"
    with pytest.raises(ValueError):
        ToleranceClass.parse("nonsense")


def test_us_customary_nominal_is_converted() -> None:
    # A 1.4 in dimension (35.6 mm) lands in the 30-120 mm range.
    g = general_tolerance(Quantity(magnitude=1.4, unit="in"), "m")
    assert g.deviation.to("mm").magnitude == pytest.approx(0.3)


def test_all_four_classes_at_50mm() -> None:
    # ISO 2768-1 f/m/c/v at the 30-120 mm range.
    expected = {"fine": 0.15, "medium": 0.3, "coarse": 0.8, "very_coarse": 1.5}
    for name, dev in expected.items():
        g = general_tolerance(_mm(50), ToleranceClass(name))
        assert g.deviation.to("mm").magnitude == pytest.approx(dev), name


def test_class_undefined_for_range_is_rejected() -> None:
    # Class v is not defined below 3 mm in ISO 2768-1.
    with pytest.raises(ToleranceRangeError, match="not defined"):
        general_tolerance(_mm(2), "v")


def test_below_minimum_requires_explicit_tolerance() -> None:
    with pytest.raises(ToleranceRangeError, match="explicit tolerance"):
        general_tolerance(_mm(0.2), "m")


def test_above_maximum_requires_explicit_tolerance() -> None:
    with pytest.raises(ToleranceRangeError, match="explicit tolerance"):
        general_tolerance(_mm(5000), "m")


def test_non_length_nominal_rejected() -> None:
    with pytest.raises(ToleranceRangeError, match="length"):
        general_tolerance(Quantity(magnitude=5, unit="kg"), "m")


# --- Angular general tolerances (ISO 2768-1) ---


def test_angular_lookup_by_shorter_leg() -> None:
    # A 30 mm shorter leg under class m falls in the 10-50 range: ±30'.
    g = general_angular_tolerance(_mm(30), ToleranceClass.MEDIUM)
    assert isinstance(g, AngularTolerance)
    assert g.deviation.to("arcminute").magnitude == pytest.approx(30)
    assert g.deviation.to("degree").magnitude == pytest.approx(0.5)
    assert "10" in g.leg_range and "50" in g.leg_range
    assert "ISO 2768-1" in g.source


def test_angular_default_class_is_medium() -> None:
    assert general_angular_tolerance(_mm(30)).tolerance_class is ToleranceClass.MEDIUM


def test_angular_fine_and_medium_share_values() -> None:
    # ISO 2768-1 gives f and m the same angular tolerance.
    assert (
        general_angular_tolerance(_mm(30), "f").deviation
        == general_angular_tolerance(_mm(30), "m").deviation
    )


def test_angular_open_top_range() -> None:
    # Any shorter leg over 400 mm resolves in the open-top range (±5' at m).
    g = general_angular_tolerance(_mm(5000), "m")
    assert g.deviation.to("arcminute").magnitude == pytest.approx(5)
    assert "over 400" in g.leg_range


def test_angular_coarse_below_10mm() -> None:
    g = general_angular_tolerance(_mm(5), "c")
    assert g.deviation.to("arcminute").magnitude == pytest.approx(90)
    assert "up to 10" in g.leg_range


def test_angular_non_length_leg_rejected() -> None:
    with pytest.raises(ToleranceRangeError, match="shorter leg"):
        general_angular_tolerance(Quantity(magnitude=5, unit="kg"), "m")
