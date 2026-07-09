"""Tests for tolerance management, tracking the tolerance-management spec."""

from __future__ import annotations

from math import sqrt

import pytest
from pydantic import TypeAdapter, ValidationError

from anvilate.tolerance import (
    AngularTolerance,
    Contribution,
    Fit,
    FitTolerance,
    GeneralTolerance,
    LimitDeviations,
    LimitTolerance,
    MonteCarloResult,
    ResolvedTolerance,
    StackContributor,
    StackResult,
    StackUp,
    StandardTolerance,
    SymmetricTolerance,
    Tolerance,
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


def test_general_tolerance_resolved_feature_sizes() -> None:
    # A 35 mm dimension under class m (±0.3 mm) permits 34.7-35.3 mm — the same
    # min_size/max_size interface a fit's LimitDeviations exposes.
    g = general_tolerance(_mm(35), "m")
    assert g.min_size.to("mm").magnitude == pytest.approx(34.7)
    assert g.max_size.to("mm").magnitude == pytest.approx(35.3)


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
    # t is a finer-stepped interference letter, not yet encoded; j is grade-dependent.
    with pytest.raises(ToleranceRangeError, match="not yet encoded"):
        zone_limits("t6", _mm(22))
    with pytest.raises(ToleranceRangeError, match="not yet encoded"):
        zone_limits("j6", _mm(22))


def test_unencoded_message_lists_the_actual_encoded_letters() -> None:
    # The supported-letters hint is derived from the encoded set, so it names the
    # letters that are actually resolvable (k/n/p/r/s/u, added after d/e/f/g)
    # rather than drifting out of date as more letters land.
    with pytest.raises(ToleranceRangeError) as excinfo:
        zone_limits("y6", _mm(22))
    message = str(excinfo.value)
    for letter in ("d", "g", "js", "k", "n", "p", "r", "s", "u"):
        assert letter in message


def test_malformed_zone_designation_rejected() -> None:
    with pytest.raises(ValueError, match="malformed"):
        zone_limits("H", _mm(22))
    with pytest.raises(ValueError, match="malformed"):
        zone_limits("7", _mm(22))


def test_zone_limits_propagates_grade_errors() -> None:
    # A nominal beyond the table surfaces as a range error from standard_tolerance.
    with pytest.raises(ToleranceRangeError, match="maximum"):
        zone_limits("H7", _mm(600))


# --- ISO 286 clearance-letter zones (d/e/f/g fundamental deviations) ---


def test_g6_shaft_limits_at_22mm() -> None:
    # g shaft at 18-30 mm: es = -7 um, ei = es - IT6 = -7 - 13 = -20 um.
    d = zone_limits("g6", _mm(22))
    assert d.hole is False
    assert d.upper.to("um").magnitude == pytest.approx(-7)
    assert d.lower.to("um").magnitude == pytest.approx(-20)
    assert d.width.to("um").magnitude == pytest.approx(13)
    assert d.max_size.to("mm").magnitude == pytest.approx(21.993)
    assert d.min_size.to("mm").magnitude == pytest.approx(21.980)


def test_f7_shaft_limits_at_20mm() -> None:
    # f shaft at 18-30 mm: es = -20 um, ei = -20 - IT7(21) = -41 um.
    d = zone_limits("f7", _mm(20))
    assert d.upper.to("um").magnitude == pytest.approx(-20)
    assert d.lower.to("um").magnitude == pytest.approx(-41)


def test_g_hole_mirrors_shaft_via_general_rule() -> None:
    # Uppercase G hole at 18-30 mm follows EI = -es(g) = +7 um, ES = EI + IT7 = +28.
    d = zone_limits("G7", _mm(22))
    assert d.hole is True
    assert d.lower.to("um").magnitude == pytest.approx(7)
    assert d.upper.to("um").magnitude == pytest.approx(28)
    assert d.width.to("um").magnitude == pytest.approx(21)


def test_f8_hole_at_22mm() -> None:
    # F hole at 18-30 mm: EI = -es(f) = +20 um, ES = +20 + IT8(33) = +53 um.
    d = zone_limits("F8", _mm(22))
    assert d.lower.to("um").magnitude == pytest.approx(20)
    assert d.upper.to("um").magnitude == pytest.approx(53)


def test_clearance_letter_smallest_size_range() -> None:
    # d shaft at <= 3 mm: es = -20 um, ei = -20 - IT9(25) = -45 um.
    d = zone_limits("d9", _mm(2))
    assert d.upper.to("um").magnitude == pytest.approx(-20)
    assert d.lower.to("um").magnitude == pytest.approx(-45)
    assert d.size_range == "up to 3 mm"


# --- ISO 286 symmetric zones (js/JS = +/- IT/2) ---


def test_js6_shaft_is_symmetric_at_22mm() -> None:
    # js6 at 18-30 mm straddles the basic size: +/- IT6/2 = +/- 6.5 um.
    d = zone_limits("js6", _mm(22))
    assert d.hole is False
    assert d.upper.to("um").magnitude == pytest.approx(6.5)
    assert d.lower.to("um").magnitude == pytest.approx(-6.5)
    assert d.width.to("um").magnitude == pytest.approx(13)


def test_uppercase_JS_hole_matches_shaft() -> None:
    # JS is the hole spelling; the symmetric zone is identical, only the role flips.
    hole = zone_limits("JS7", _mm(22))
    shaft = zone_limits("js7", _mm(22))
    assert hole.hole is True and shaft.hole is False
    assert hole.upper == shaft.upper and hole.lower == shaft.lower
    # IT7 = 21 um at 18-30 mm, so +/- 10.5 um.
    assert hole.upper.to("um").magnitude == pytest.approx(10.5)


def test_h7js6_transition_fit_at_22mm() -> None:
    # H7/js6 at 22 mm: hole 0..+21 um, shaft +/-6.5 um. Min clearance 0 - 6.5 =
    # -6.5 um (slight interference); max clearance 21 - (-6.5) = +27.5 um.
    f = fit("H7/js6", _mm(22))
    assert f.kind == "transition"
    assert f.min_clearance.to("um").magnitude == pytest.approx(-6.5)
    assert f.max_clearance.to("um").magnitude == pytest.approx(27.5)


# --- ISO 286 transition/interference shaft zones (m/n/p, positive ei) ---


def test_p6_shaft_limits_at_22mm() -> None:
    # p shaft at 18-30 mm: ei = +22 um, es = ei + IT6 = 22 + 13 = +35 um.
    d = zone_limits("p6", _mm(22))
    assert d.hole is False
    assert d.lower.to("um").magnitude == pytest.approx(22)
    assert d.upper.to("um").magnitude == pytest.approx(35)
    assert d.min_size.to("mm").magnitude == pytest.approx(22.022)
    assert d.max_size.to("mm").magnitude == pytest.approx(22.035)


def test_n6_and_m6_shaft_ei_at_22mm() -> None:
    # n shaft ei = +15, es = 15 + 13 = +28 um; m shaft ei = +8, es = 8 + 13 = +21.
    n = zone_limits("n6", _mm(22))
    assert n.lower.to("um").magnitude == pytest.approx(15)
    assert n.upper.to("um").magnitude == pytest.approx(28)
    m = zone_limits("m6", _mm(22))
    assert m.lower.to("um").magnitude == pytest.approx(8)
    assert m.upper.to("um").magnitude == pytest.approx(21)


# --- ISO 286 grade-banded k transition shaft ---


def test_k6_and_k7_shaft_at_22mm() -> None:
    # k shaft ei = +2 um at 18-30 mm (grades IT4-IT7). k6: es = 2 + IT6(13) = +15;
    # k7: es = 2 + IT7(21) = +23.
    k6 = zone_limits("k6", _mm(22))
    assert k6.hole is False
    assert k6.lower.to("um").magnitude == pytest.approx(2)
    assert k6.upper.to("um").magnitude == pytest.approx(15)
    k7 = zone_limits("k7", _mm(22))
    assert k7.lower.to("um").magnitude == pytest.approx(2)
    assert k7.upper.to("um").magnitude == pytest.approx(23)


def test_k_shaft_zero_outside_grade_band() -> None:
    # Outside IT4-IT7 the k fundamental deviation collapses to zero, so k8 sits on
    # the basic size like an h shaft: ei = 0, es = IT8(33) = +33 um.
    k8 = zone_limits("k8", _mm(22))
    assert k8.lower.to("um").magnitude == pytest.approx(0)
    assert k8.upper.to("um").magnitude == pytest.approx(33)


def test_k_hole_delta_corrected_at_22mm() -> None:
    # K hole via ES = -ei + Δ with the k-shaft ei = +2 um at 18-30 mm.
    # K7: Δ = IT7 - IT6 = 8, ES = -2 + 8 = +6, EI = +6 - 21 = -15.
    k7 = zone_limits("K7", _mm(22))
    assert k7.hole is True
    assert k7.upper.to("um").magnitude == pytest.approx(6)
    assert k7.lower.to("um").magnitude == pytest.approx(-15)
    # K6: Δ = IT6 - IT5 = 4, ES = -2 + 4 = +2, EI = +2 - 13 = -11.
    k6 = zone_limits("K6", _mm(22))
    assert k6.upper.to("um").magnitude == pytest.approx(2)
    assert k6.lower.to("um").magnitude == pytest.approx(-11)


def test_k_hole_capped_at_it7() -> None:
    # The K hole is capped at IT7 so its k-shaft ei stays inside the IT4-IT7 band.
    with pytest.raises(ToleranceRangeError, match="out of range"):
        zone_limits("K8", _mm(22))


def test_h7k6_transition_fit_at_22mm() -> None:
    # H7/k6 at 22 mm: hole 0..+21 um, shaft +2..+15 um. Min clearance 0 - 15 =
    # -15 um; max clearance 21 - 2 = +19 um => transition.
    f = fit("H7/k6", _mm(22))
    assert f.kind == "transition"
    assert f.min_clearance.to("um").magnitude == pytest.approx(-15)
    assert f.max_clearance.to("um").magnitude == pytest.approx(19)


# --- ISO 286 finer-stepped r/s interference shafts (<= 50 mm) ---


def test_s6_and_r6_shaft_at_22mm() -> None:
    # At 18-30 mm: s ei = +35 um, es = 35 + IT6(13) = +48; r ei = +28, es = +41.
    s6 = zone_limits("s6", _mm(22))
    assert s6.hole is False
    assert s6.lower.to("um").magnitude == pytest.approx(35)
    assert s6.upper.to("um").magnitude == pytest.approx(48)
    r6 = zone_limits("r6", _mm(22))
    assert r6.lower.to("um").magnitude == pytest.approx(28)
    assert r6.upper.to("um").magnitude == pytest.approx(41)


def test_rs_shaft_above_50mm_rejected() -> None:
    # Above 50 mm r/s split into finer diameter steps this table does not carry.
    with pytest.raises(ToleranceRangeError, match="up to 50 mm"):
        zone_limits("s6", _mm(60))
    with pytest.raises(ToleranceRangeError, match="up to 50 mm"):
        zone_limits("r6", _mm(60))


def test_rs_holes_delta_corrected_at_22mm() -> None:
    # R/S holes via ES = -ei + Δ with the r/s shaft ei at 18-30 mm (r=+28, s=+35).
    # S7: Δ = IT7 - IT6 = 8, ES = -35 + 8 = -27, EI = -27 - 21 = -48.
    s7 = zone_limits("S7", _mm(22))
    assert s7.hole is True
    assert s7.upper.to("um").magnitude == pytest.approx(-27)
    assert s7.lower.to("um").magnitude == pytest.approx(-48)
    # R6: Δ = IT6 - IT5 = 4, ES = -28 + 4 = -24, EI = -24 - 13 = -37.
    r6 = zone_limits("R6", _mm(22))
    assert r6.upper.to("um").magnitude == pytest.approx(-24)
    assert r6.lower.to("um").magnitude == pytest.approx(-37)


def test_rs_hole_capped_at_it7_and_50mm() -> None:
    with pytest.raises(ToleranceRangeError, match="out of range"):
        zone_limits("S8", _mm(22))
    with pytest.raises(ToleranceRangeError, match="up to 50 mm"):
        zone_limits("S7", _mm(60))


def test_h7s6_interference_fit_at_22mm() -> None:
    # H7/s6 at 22 mm (the standard drive/press fit): hole 0..+21 um, shaft
    # +35..+48 um. Min clearance 0 - 48 = -48 um; max clearance 21 - 35 = -14 um;
    # both negative => interference.
    f = fit("H7/s6", _mm(22))
    assert f.kind == "interference"
    assert f.min_clearance.to("um").magnitude == pytest.approx(-48)
    assert f.max_clearance.to("um").magnitude == pytest.approx(-14)


# --- ISO 286 heavy u interference shaft (<= 18 mm) ---


def test_u6_shaft_at_15mm() -> None:
    # At 10-18 mm: u ei = +33 um, es = 33 + IT6(11) = +44.
    u6 = zone_limits("u6", _mm(15))
    assert u6.hole is False
    assert u6.lower.to("um").magnitude == pytest.approx(33)
    assert u6.upper.to("um").magnitude == pytest.approx(44)
    assert u6.min_size.to("mm").magnitude == pytest.approx(15.033)
    assert u6.max_size.to("mm").magnitude == pytest.approx(15.044)


def test_u_shaft_above_18mm_rejected() -> None:
    # Above 18 mm u splits the 18-30 coarse step into 18-24/24-30, so its tabulated
    # value is no longer exact and the lookup is rejected.
    with pytest.raises(ToleranceRangeError, match="up to 18 mm"):
        zone_limits("u6", _mm(22))


def test_u_holes_delta_corrected_at_15mm() -> None:
    # U holes via ES = -ei + Δ with the u shaft ei = +33 um at 10-18 mm.
    # IT5=8, IT6=11, IT7=18 um.
    # U7: Δ = IT7 - IT6 = 7, ES = -33 + 7 = -26, EI = -26 - 18 = -44.
    u7 = zone_limits("U7", _mm(15))
    assert u7.hole is True
    assert u7.upper.to("um").magnitude == pytest.approx(-26)
    assert u7.lower.to("um").magnitude == pytest.approx(-44)
    # U6: Δ = IT6 - IT5 = 3, ES = -33 + 3 = -30, EI = -30 - 11 = -41.
    u6 = zone_limits("U6", _mm(15))
    assert u6.upper.to("um").magnitude == pytest.approx(-30)
    assert u6.lower.to("um").magnitude == pytest.approx(-41)


def test_u_hole_capped_at_it7_and_18mm() -> None:
    with pytest.raises(ToleranceRangeError, match="out of range"):
        zone_limits("U8", _mm(15))
    with pytest.raises(ToleranceRangeError, match="up to 18 mm"):
        zone_limits("U7", _mm(22))


def test_h7u6_interference_fit_at_15mm() -> None:
    # H7/u6 at 15 mm (a heavy press fit): hole 0..+18 um, shaft +33..+44 um.
    # Min clearance 0 - 44 = -44 um; max clearance 18 - 33 = -15 um; both
    # negative => interference.
    f = fit("H7/u6", _mm(15))
    assert f.kind == "interference"
    assert f.min_clearance.to("um").magnitude == pytest.approx(-44)
    assert f.max_clearance.to("um").magnitude == pytest.approx(-15)


# --- ISO 286 delta-corrected interference/transition holes (M/N/P) ---


def test_np_holes_delta_corrected_at_22mm() -> None:
    # ISO 286 special rule ES = -ei + Δ, Δ = IT_n − IT_(n−1), at 18-30 mm.
    # IT5=9, IT6=13, IT7=21 um; ei: m=8, n=15, p=22 um.
    # N7: Δ = 21-13 = 8, ES = -15+8 = -7, EI = -7-21 = -28.
    n7 = zone_limits("N7", _mm(22))
    assert n7.hole is True
    assert n7.upper.to("um").magnitude == pytest.approx(-7)
    assert n7.lower.to("um").magnitude == pytest.approx(-28)
    # P7: ES = -22+8 = -14, EI = -14-21 = -35.
    p7 = zone_limits("P7", _mm(22))
    assert p7.upper.to("um").magnitude == pytest.approx(-14)
    assert p7.lower.to("um").magnitude == pytest.approx(-35)
    # M7: ES = -8+8 = 0, EI = 0-21 = -21.
    m7 = zone_limits("M7", _mm(22))
    assert m7.upper.to("um").magnitude == pytest.approx(0)
    assert m7.lower.to("um").magnitude == pytest.approx(-21)


def test_mnp_holes_delta_corrected_at_it6() -> None:
    # At IT6, Δ = IT6 − IT5 = 13 - 9 = 4 um (18-30 mm range).
    # M6: ES = -8+4 = -4, EI = -4-13 = -17.
    m6 = zone_limits("M6", _mm(22))
    assert m6.upper.to("um").magnitude == pytest.approx(-4)
    assert m6.lower.to("um").magnitude == pytest.approx(-17)
    # N6: ES = -15+4 = -11, EI = -11-13 = -24.
    n6 = zone_limits("N6", _mm(22))
    assert n6.upper.to("um").magnitude == pytest.approx(-11)
    assert n6.lower.to("um").magnitude == pytest.approx(-24)
    # P6: ES = -22+4 = -18, EI = -18-13 = -31.
    p6 = zone_limits("P6", _mm(22))
    assert p6.upper.to("um").magnitude == pytest.approx(-18)
    assert p6.lower.to("um").magnitude == pytest.approx(-31)


def test_delta_hole_out_of_grade_band_rejected() -> None:
    # The special rule caps at N8/M8 and P7; finer than IT6 needs IT below IT5.
    with pytest.raises(ToleranceRangeError, match="out of range"):
        zone_limits("P8", _mm(22))
    with pytest.raises(ToleranceRangeError, match="out of range"):
        zone_limits("N9", _mm(22))
    with pytest.raises(ToleranceRangeError, match="out of range"):
        zone_limits("M5", _mm(22))


def test_n7h6_shaft_basis_transition_fit_at_22mm() -> None:
    # N7/h6 at 22 mm: hole -7..-28 um, shaft 0..-13 um. Min clearance -28 - 0 =
    # -28 um; max clearance -7 - (-13) = +6 um => transition (shaft-basis mirror
    # of H7/n6).
    f = fit("N7/h6", _mm(22))
    assert f.kind == "transition"
    assert f.min_clearance.to("um").magnitude == pytest.approx(-28)
    assert f.max_clearance.to("um").magnitude == pytest.approx(6)


def test_h7p6_interference_fit_at_22mm() -> None:
    # H7/p6 at 22 mm: hole 0..+21 um, shaft +22..+35 um. Min clearance 0 - 35 =
    # -35 um; max clearance 21 - 22 = -1 um. Both negative => interference.
    f = fit("H7/p6", _mm(22))
    assert f.kind == "interference"
    assert f.min_clearance.to("um").magnitude == pytest.approx(-35)
    assert f.max_clearance.to("um").magnitude == pytest.approx(-1)


def test_h7n6_transition_fit_at_22mm() -> None:
    # H7/n6 at 22 mm: hole 0..+21 um, shaft +15..+28 um. Min clearance -28 um;
    # max clearance 21 - 15 = +6 um => transition.
    f = fit("H7/n6", _mm(22))
    assert f.kind == "transition"
    assert f.min_clearance.to("um").magnitude == pytest.approx(-28)
    assert f.max_clearance.to("um").magnitude == pytest.approx(6)


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
        fit("H7/t6", _mm(22))


def test_h7g6_sliding_fit_at_22mm() -> None:
    # The spec's fit-resolution example. H7/g6 at 22 mm: hole 0..+21 um, shaft
    # -20..-7 um. Min clearance 0 - (-7) = +7 um; max clearance 21 - (-20) = +41 um.
    f = fit("H7/g6", _mm(22))
    assert f.kind == "clearance"
    assert f.min_clearance.to("um").magnitude == pytest.approx(7)
    assert f.max_clearance.to("um").magnitude == pytest.approx(41)
    assert f.designation == "H7/g6"


def test_h8f7_running_fit_at_50mm() -> None:
    # H8/f7 at 50 mm (30-50 range): hole 0..+39 um, shaft es=-25, ei=-25-25=-50 um.
    # Min clearance 25 um; max clearance 39 - (-50) = 89 um.
    f = fit("H8/f7", _mm(50))
    assert f.kind == "clearance"
    assert f.min_clearance.to("um").magnitude == pytest.approx(25)
    assert f.max_clearance.to("um").magnitude == pytest.approx(89)


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


# --- Explicit per-dimension tolerances (symmetric / limits / fit) ---


def test_symmetric_tolerance_resolves_to_band() -> None:
    r = SymmetricTolerance(plus_minus=_mm(0.1)).resolve(_mm(35))
    assert isinstance(r, ResolvedTolerance)
    assert r.upper.to("mm").magnitude == pytest.approx(0.1)
    assert r.lower.to("mm").magnitude == pytest.approx(-0.1)
    assert r.min_size.to("mm").magnitude == pytest.approx(34.9)
    assert r.max_size.to("mm").magnitude == pytest.approx(35.1)
    assert r.width.to("mm").magnitude == pytest.approx(0.2)
    assert r.source is None


def test_symmetric_tolerance_rejects_negative() -> None:
    with pytest.raises(ValidationError, match="non-negative"):
        SymmetricTolerance(plus_minus=_mm(-0.1))


def test_limit_tolerance_resolves_asymmetric_band() -> None:
    r = LimitTolerance(upper=_mm(0.05), lower=_mm(-0.02)).resolve(_mm(10))
    assert r.min_size.to("mm").magnitude == pytest.approx(9.98)
    assert r.max_size.to("mm").magnitude == pytest.approx(10.05)
    assert r.source is None


def test_limit_tolerance_rejects_inverted_bounds() -> None:
    with pytest.raises(ValidationError, match="at least the lower"):
        LimitTolerance(upper=_mm(-0.05), lower=_mm(0.02))


def test_fit_tolerance_resolves_through_iso286() -> None:
    # An explicit `fit: H7` at 22 mm resolves the ISO 286 zone: 0..+0.021 mm,
    # carrying the ISO citation. This is the spec's fit-resolution scenario.
    r = FitTolerance(designation="H7").resolve(_mm(22))
    assert r.label == "H7"
    assert r.lower.to("mm").magnitude == pytest.approx(0.0)
    assert r.upper.to("mm").magnitude == pytest.approx(0.021)
    assert r.min_size.to("mm").magnitude == pytest.approx(22.0)
    assert r.max_size.to("mm").magnitude == pytest.approx(22.021)
    assert "ISO 286-1" in r.source


def test_fit_tolerance_propagates_unencoded_zone() -> None:
    with pytest.raises(ToleranceRangeError, match="not yet encoded"):
        FitTolerance(designation="t6").resolve(_mm(22))


def test_tolerance_union_discriminates_by_type() -> None:
    # The Tolerance union is the field type a Spec IR dimension will carry; the
    # `type` tag selects the variant when parsed from a spec's data.
    adapter = TypeAdapter(Tolerance)
    sym = adapter.validate_python(
        {"type": "symmetric", "plus_minus": {"magnitude": 0.1, "unit": "mm"}}
    )
    assert isinstance(sym, SymmetricTolerance)
    fit_t = adapter.validate_python({"type": "fit", "designation": "g6"})
    assert isinstance(fit_t, FitTolerance)
    with pytest.raises(ValidationError):
        adapter.validate_python({"type": "nonsense"})


def _contributor(name: str, nominal: float, pm: float, direction: int = 1) -> StackContributor:
    # A symmetric ± dimension resolved onto a stack contributor, via the real
    # SymmetricTolerance.resolve path.
    resolved = SymmetricTolerance(plus_minus=_mm(pm)).resolve(_mm(nominal))
    return StackContributor(name=name, tolerance=resolved, direction=direction)


def test_stackup_interface_gap_worst_case_and_rss() -> None:
    # Scenario: interface gap stack-up — a chain from a mount face (+) through a
    # flange thickness (-) to a motor pilot seat (-) yields a nominal 0.3 mm gap.
    stack = StackUp(
        contributors=(
            _contributor("mount face", 20.0, 0.05, direction=1),
            _contributor("flange thickness", 12.0, 0.03, direction=-1),
            _contributor("pilot seat", 7.7, 0.02, direction=-1),
        )
    )

    wc = stack.worst_case()
    assert isinstance(wc, StackResult)
    assert wc.method == "worst_case"
    assert wc.nominal.to("mm").magnitude == pytest.approx(0.3)
    # Worst case adds every half-width: 0.05 + 0.03 + 0.02 = 0.10.
    assert wc.lower.to("mm").magnitude == pytest.approx(0.20)
    assert wc.upper.to("mm").magnitude == pytest.approx(0.40)
    assert wc.width.to("mm").magnitude == pytest.approx(0.20)

    rss = stack.rss()
    assert rss.method == "rss"
    assert rss.nominal.to("mm").magnitude == pytest.approx(0.3)
    # RSS adds in quadrature: sqrt(0.05^2 + 0.03^2 + 0.02^2) = 0.0616441.
    assert rss.upper.to("mm").magnitude == pytest.approx(0.3616441, abs=1e-6)
    assert rss.lower.to("mm").magnitude == pytest.approx(0.2383559, abs=1e-6)
    # RSS is always tighter than worst-case.
    assert rss.width.to("mm").magnitude < wc.width.to("mm").magnitude


def test_stackup_contributions_ranked_and_normalized() -> None:
    stack = StackUp(
        contributors=(
            _contributor("mount face", 20.0, 0.05, direction=1),
            _contributor("flange thickness", 12.0, 0.03, direction=-1),
            _contributor("pilot seat", 7.7, 0.02, direction=-1),
        )
    )

    wc = stack.worst_case()
    assert all(isinstance(c, Contribution) for c in wc.contributions)
    # Ranked widest-share first, and shares sum to 1.
    assert [c.name for c in wc.contributions] == ["mount face", "flange thickness", "pilot seat"]
    assert [c.share for c in wc.contributions] == pytest.approx([0.5, 0.3, 0.2])
    assert sum(c.share for c in wc.contributions) == pytest.approx(1.0)

    rss = stack.rss()
    # RSS splits on squared half-widths, so the widest dimension dominates more.
    assert rss.contributions[0].name == "mount face"
    assert rss.contributions[0].share == pytest.approx(0.0025 / 0.0038)
    assert sum(c.share for c in rss.contributions) == pytest.approx(1.0)


def test_stackup_satisfies_required_gap_band() -> None:
    stack = StackUp(
        contributors=(
            _contributor("mount face", 20.0, 0.05, direction=1),
            _contributor("flange thickness", 12.0, 0.03, direction=-1),
            _contributor("pilot seat", 7.7, 0.02, direction=-1),
        )
    )
    # Worst-case gap [0.20, 0.40] fits the required 0.1-0.5 mm clearance.
    assert stack.worst_case().satisfies(_mm(0.1), _mm(0.5)) is True
    # Tighten the requirement past the worst-case lower bound and it fails.
    assert stack.worst_case().satisfies(_mm(0.25), _mm(0.5)) is False
    # RSS is tighter, so it can pass a requirement worst-case fails.
    assert stack.rss().satisfies(_mm(0.23), _mm(0.37)) is True
    assert stack.worst_case().satisfies(_mm(0.23), _mm(0.37)) is False


def test_stackup_recentres_asymmetric_tolerance() -> None:
    # An asymmetric zone (+0.02 / -0.06) recentres on its mean before stacking:
    # mean size 9.98 mm, half-width 0.04 mm.
    asym = LimitTolerance(upper=_mm(0.02), lower=_mm(-0.06)).resolve(_mm(10.0))
    stack = StackUp(contributors=(StackContributor(name="pin", tolerance=asym, direction=1),))
    wc = stack.worst_case()
    assert wc.nominal.to("mm").magnitude == pytest.approx(9.98)
    assert wc.lower.to("mm").magnitude == pytest.approx(9.94)
    assert wc.upper.to("mm").magnitude == pytest.approx(10.02)
    assert wc.contributions[0].half_width.to("mm").magnitude == pytest.approx(0.04)


def test_stackup_rejects_empty_chain() -> None:
    with pytest.raises(ValidationError):
        StackUp(contributors=())


def test_stackup_satisfies_rejects_non_length_requirement() -> None:
    stack = StackUp(contributors=(_contributor("pin", 10.0, 0.02),))
    with pytest.raises(ValueError, match="must be a length"):
        stack.worst_case().satisfies(Quantity(magnitude=1, unit="deg"), _mm(0.5))


def test_stackup_result_str_renders_band() -> None:
    stack = StackUp(contributors=(_contributor("pin", 10.0, 0.02),))
    assert "worst_case" in str(stack.worst_case())


def _interface_stack() -> StackUp:
    return StackUp(
        contributors=(
            _contributor("mount face", 20.0, 0.05, direction=1),
            _contributor("flange thickness", 12.0, 0.03, direction=-1),
            _contributor("pilot seat", 7.7, 0.02, direction=-1),
        )
    )


def test_monte_carlo_normal_matches_rss_band() -> None:
    # Scenario: with every dimension normal and the band read as ±3σ, the central
    # 99.73% Monte Carlo band should reproduce the analytic RSS gap.
    stack = _interface_stack()
    mc = stack.monte_carlo(20000, seed=7)
    rss = stack.rss()

    assert isinstance(mc, MonteCarloResult)
    assert mc.method == "monte_carlo"
    assert mc.samples == 20000
    # Analytic nominal gap is exact; the sampled mean lands near it.
    assert mc.nominal.to("mm").magnitude == pytest.approx(0.3)
    assert mc.mean.to("mm").magnitude == pytest.approx(0.3, abs=0.002)
    # Sampled std ≈ RSS half-width / 3, and the ±3σ band ≈ the RSS band.
    assert mc.std.to("mm").magnitude == pytest.approx(0.0616441 / 3.0, rel=0.03)
    assert mc.lower.to("mm").magnitude == pytest.approx(rss.lower.to("mm").magnitude, abs=0.004)
    assert mc.upper.to("mm").magnitude == pytest.approx(rss.upper.to("mm").magnitude, abs=0.004)


def test_monte_carlo_is_deterministic_for_a_seed() -> None:
    stack = _interface_stack()
    a = stack.monte_carlo(5000, seed=42)
    b = stack.monte_carlo(5000, seed=42)
    assert a.mean.to("mm").magnitude == b.mean.to("mm").magnitude
    assert a.sorted_gaps_mm == b.sorted_gaps_mm
    # A different seed shifts the sampled mean.
    c = stack.monte_carlo(5000, seed=43)
    assert c.mean.to("mm").magnitude != a.mean.to("mm").magnitude


def test_monte_carlo_predicts_yield_against_a_band() -> None:
    stack = _interface_stack()
    mc = stack.monte_carlo(20000, seed=11)
    # The worst-case gap [0.20, 0.40] fully contains the spread: yield ≈ 1.
    assert mc.yield_fraction(_mm(0.1), _mm(0.5)) == pytest.approx(1.0, abs=1e-3)
    # Scoring the reported coverage band recovers the coverage fraction.
    assert mc.yield_fraction(mc.lower, mc.upper) == pytest.approx(mc.coverage, abs=0.01)
    # A band clipped around the mean passes only part of the run.
    partial = mc.yield_fraction(_mm(0.30), _mm(0.5))
    assert 0.4 < partial < 0.6


def test_monte_carlo_uniform_spreads_wider_than_normal() -> None:
    resolved = SymmetricTolerance(plus_minus=_mm(0.05)).resolve(_mm(10.0))
    normal = StackUp(
        contributors=(StackContributor(name="pin", tolerance=resolved, distribution="normal"),)
    )
    uniform = StackUp(
        contributors=(StackContributor(name="pin", tolerance=resolved, distribution="uniform"),)
    )
    # Uniform std = half/sqrt(3) ≈ 0.577·half; normal (±3σ) std = half/3 ≈ 0.333·half.
    assert normal.monte_carlo(20000, seed=3).std.to("mm").magnitude == pytest.approx(
        0.05 / 3.0, rel=0.03
    )
    assert uniform.monte_carlo(20000, seed=3).std.to("mm").magnitude == pytest.approx(
        0.05 / sqrt(3.0), rel=0.03
    )


def test_monte_carlo_contributions_rank_by_variance() -> None:
    mc = _interface_stack().monte_carlo(2000, seed=1)
    # Variance shares match RSS's squared-half-width split (sigma_level cancels).
    assert mc.contributions[0].name == "mount face"
    assert mc.contributions[0].share == pytest.approx(0.0025 / 0.0038)
    assert sum(c.share for c in mc.contributions) == pytest.approx(1.0)


def test_monte_carlo_str_renders_band_and_coverage() -> None:
    mc = _interface_stack().monte_carlo(1000, seed=5)
    text = str(mc)
    assert "monte_carlo" in text
    assert "99.73%" in text


def test_monte_carlo_yield_rejects_non_length_requirement() -> None:
    mc = _interface_stack().monte_carlo(1000, seed=5)
    with pytest.raises(ValueError, match="must be a length"):
        mc.yield_fraction(Quantity(magnitude=1, unit="deg"), _mm(0.5))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"samples": 1, "seed": 0},
        {"samples": 100, "seed": 0, "sigma_level": 0.0},
        {"samples": 100, "seed": 0, "coverage": 0.0},
        {"samples": 100, "seed": 0, "coverage": 1.0},
    ],
)
def test_monte_carlo_rejects_bad_arguments(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        _interface_stack().monte_carlo(**kwargs)
