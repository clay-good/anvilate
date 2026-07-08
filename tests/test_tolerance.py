"""Tests for tolerance management, tracking the tolerance-management spec."""

from __future__ import annotations

import pytest

from anvilate.tolerance import (
    AngularTolerance,
    Fit,
    GeneralTolerance,
    LimitDeviations,
    StandardTolerance,
    ToleranceClass,
    ToleranceRangeError,
    fit,
    general_angular_tolerance,
    general_tolerance,
    resolve_class,
    standard_tolerance,
    zone_limits,
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


def test_resolve_class_defaults_to_medium_when_unset() -> None:
    # Scenario: default class applied — a spec that omits tolerance info (None)
    # is governed by the medium class; a present value is parsed.
    assert resolve_class(None) is ToleranceClass.MEDIUM
    assert resolve_class("fine") is ToleranceClass.FINE
    assert resolve_class("c") is ToleranceClass.COARSE
    with pytest.raises(ValueError):
        resolve_class("nonsense")


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


# --- ISO 286-1 standard tolerance grades (IT grades) ---


def test_it7_at_22mm_with_citation() -> None:
    # The grade half of the spec's `fit: H7` at 22 mm nominal: 22 mm is in the
    # 18-30 mm range, where IT7 is 21 um.
    t = standard_tolerance(_mm(22), 7)
    assert isinstance(t, StandardTolerance)
    assert t.width.to("um").magnitude == pytest.approx(21)
    assert t.width.to("mm").magnitude == pytest.approx(0.021)
    assert "18" in t.size_range and "30" in t.size_range
    assert t.designation == "IT7"
    assert "ISO 286-1" in t.source


def test_grade_parses_from_int_or_string() -> None:
    assert standard_tolerance(_mm(22), "IT7").grade == 7
    assert standard_tolerance(_mm(22), "7").grade == 7
    assert standard_tolerance(_mm(22), "it7").width == standard_tolerance(_mm(22), 7).width
    with pytest.raises(ValueError, match="unrecognized IT grade"):
        standard_tolerance(_mm(22), "H7")


def test_grade_range_boundary_is_inclusive_of_upper() -> None:
    # 30 mm belongs to the 18-30 range (IT7 = 21 um), not the 30-50 range (25 um).
    assert standard_tolerance(_mm(30), 7).width.to("um").magnitude == pytest.approx(21)
    assert standard_tolerance(_mm(50), 7).width.to("um").magnitude == pytest.approx(25)


def test_first_range_label_and_smallest_size() -> None:
    t = standard_tolerance(_mm(2), 6)
    assert t.size_range == "up to 3 mm"
    assert t.width.to("um").magnitude == pytest.approx(6)


def test_coarse_grade_spans_range() -> None:
    # IT16 at 400-500 mm is 4000 um (4 mm) — the widest encoded value.
    t = standard_tolerance(_mm(450), 16)
    assert t.width.to("mm").magnitude == pytest.approx(4.0)
    assert "over 400 up to 500 mm" == t.size_range


def test_grade_us_customary_nominal_is_converted() -> None:
    # 1 in is 25.4 mm, landing in the 18-30 mm range: IT7 = 21 um.
    t = standard_tolerance(Quantity(magnitude=1.0, unit="in"), 7)
    assert t.width.to("um").magnitude == pytest.approx(21)


def test_ungraded_grade_rejected() -> None:
    with pytest.raises(ToleranceRangeError, match="not in the encoded"):
        standard_tolerance(_mm(22), 3)


def test_zero_and_oversize_nominal_rejected() -> None:
    with pytest.raises(ToleranceRangeError, match="greater than 0"):
        standard_tolerance(_mm(0), 7)
    with pytest.raises(ToleranceRangeError, match="maximum"):
        standard_tolerance(_mm(600), 7)


def test_standard_tolerance_non_length_rejected() -> None:
    with pytest.raises(ToleranceRangeError, match="length"):
        standard_tolerance(Quantity(magnitude=5, unit="kg"), 7)


# --- ISO 286 H/h basis limit deviations ---


def test_h7_hole_limits_at_22mm() -> None:
    # Scenario: `fit: H7` at 22 mm nominal (hole side). H hole has EI = 0 and
    # ES = +IT7 = +0.021 mm; the bore runs 22.000-22.021 mm.
    d = zone_limits("H7", _mm(22))
    assert isinstance(d, LimitDeviations)
    assert d.hole is True
    assert d.grade == 7
    assert d.lower.to("mm").magnitude == pytest.approx(0.0)
    assert d.upper.to("mm").magnitude == pytest.approx(0.021)
    assert d.width.to("um").magnitude == pytest.approx(21)
    assert "ISO 286-1" in d.source


def test_zone_limits_resolved_feature_sizes() -> None:
    # The deviations become the actual bore/shaft bounds a drawing states.
    bore = zone_limits("H7", _mm(22))
    assert bore.min_size.to("mm").magnitude == pytest.approx(22.000)
    assert bore.max_size.to("mm").magnitude == pytest.approx(22.021)
    shaft = zone_limits("h6", _mm(22))
    assert shaft.min_size.to("mm").magnitude == pytest.approx(21.987)
    assert shaft.max_size.to("mm").magnitude == pytest.approx(22.000)


def test_h6_shaft_limits_at_22mm() -> None:
    # h shaft: es = 0, ei = -IT6 = -0.013 mm at 18-30 mm.
    d = zone_limits("h6", _mm(22))
    assert d.hole is False
    assert d.upper.to("mm").magnitude == pytest.approx(0.0)
    assert d.lower.to("mm").magnitude == pytest.approx(-0.013)
    assert d.width.to("um").magnitude == pytest.approx(13)


def test_zone_limits_designation_normalized() -> None:
    assert zone_limits("H7", _mm(22)).designation == "H7"
    assert str(zone_limits("H7", _mm(22))) == "22 mm H7 (+0.021 / +0.000 mm)"


def test_unencoded_zone_letter_rejected() -> None:
    with pytest.raises(ToleranceRangeError, match="not yet encoded"):
        zone_limits("g6", _mm(22))


def test_malformed_zone_designation_rejected() -> None:
    with pytest.raises(ValueError, match="malformed"):
        zone_limits("H", _mm(22))
    with pytest.raises(ValueError, match="malformed"):
        zone_limits("7", _mm(22))


def test_zone_limits_propagates_grade_errors() -> None:
    # A nominal beyond the table surfaces as a range error from standard_tolerance.
    with pytest.raises(ToleranceRangeError, match="maximum"):
        zone_limits("H7", _mm(600))


# --- ISO 286 fits (hole/shaft pairs) ---


def test_h7h6_slip_fit_at_22mm() -> None:
    # H7/h6 at 22 mm is a clearance fit with zero minimum: hole 0..+21 um,
    # shaft -13..0 um. Min clearance 0, max clearance 34 um.
    f = fit("H7/h6", _mm(22))
    assert isinstance(f, Fit)
    assert f.kind == "clearance"
    assert f.min_clearance.to("um").magnitude == pytest.approx(0)
    assert f.max_clearance.to("um").magnitude == pytest.approx(34)
    assert f.designation == "H7/h6"
    assert f.hole.hole is True and f.shaft.hole is False


def test_fit_str_renders_range() -> None:
    assert str(fit("H7/h6", _mm(22))) == "22 mm H7/h6 clearance (+0.000 to +0.034 mm)"


def test_fit_requires_hole_then_shaft() -> None:
    # Two shafts, or shaft-then-hole, are not a valid fit ordering.
    with pytest.raises(ValueError, match="hole/shaft"):
        fit("h7/h6", _mm(22))
    with pytest.raises(ValueError, match="hole/shaft"):
        fit("h6/H7", _mm(22))


def test_fit_malformed_designation_rejected() -> None:
    with pytest.raises(ValueError, match="malformed fit"):
        fit("H7", _mm(22))
    with pytest.raises(ValueError, match="malformed fit"):
        fit("H7/h6/x5", _mm(22))


def test_fit_propagates_unencoded_zone() -> None:
    with pytest.raises(ToleranceRangeError, match="not yet encoded"):
        fit("H7/g6", _mm(22))


def test_fit_satisfies_clearance_requirement() -> None:
    # H7/h6 at 22 mm gives clearance 0..0.034 mm. A required 0..0.05 mm band
    # contains it; a required 0.01..0.05 mm band excludes the zero minimum.
    f = fit("H7/h6", _mm(22))
    assert f.satisfies_clearance(_mm(0.0), _mm(0.05)) is True
    assert f.satisfies_clearance(_mm(0.01), _mm(0.05)) is False  # min clearance 0 < 0.01
    assert f.satisfies_clearance(_mm(0.0), _mm(0.03)) is False  # max clearance 0.034 > 0.03


def test_fit_satisfies_clearance_rejects_non_length() -> None:
    f = fit("H7/h6", _mm(22))
    with pytest.raises(ToleranceRangeError, match="length"):
        f.satisfies_clearance(Quantity(magnitude=1, unit="kg"), _mm(0.05))
