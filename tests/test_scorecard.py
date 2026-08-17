"""Tests for the scorecard entry vocabulary and the No-silent-green rule."""

from __future__ import annotations

import pytest

from anvilate.scorecard import (
    CheckStatus,
    Direction,
    GoverningChange,
    RepairHint,
    Scorecard,
    ScorecardEntry,
)


def test_safety_factor_pass_and_fail():
    ok = ScorecardEntry.from_safety_factor("bending", computed=2.0, required=1.5)
    assert ok.status is CheckStatus.PASS
    assert ok.passed and ok.evaluated
    assert "2.00" in ok.detail

    bad = ScorecardEntry.from_safety_factor("bending", computed=1.2, required=1.5)
    assert bad.status is CheckStatus.FAIL
    assert not bad.passed
    assert bad.evaluated  # it ran; it just failed


def test_utilization_pins_its_documented_one_point_zero_threshold():
    # utilization is public and its docstring says "1.0 sits exactly at the limit, above 1.0 is a
    # failure" -- but it was consumed only as a max() ordering key and rendered into strings whose
    # NAMES are asserted. A common scale changes no ordering and no name, so the 1.0 threshold
    # that is the property's entire meaning was pinned nowhere.
    comfortable = ScorecardEntry.from_safety_factor("bearing", computed=1.8, required=1.5)
    assert comfortable.utilization == pytest.approx(0.8333333333333334, rel=1e-12)
    assert comfortable.utilization < 1.0

    at_limit = ScorecardEntry.from_safety_factor("axial", computed=1.5, required=1.5)
    assert at_limit.utilization == pytest.approx(1.0, rel=1e-12)
    assert at_limit.passed

    over = ScorecardEntry.from_safety_factor("shear", computed=1.0, required=1.5)
    assert over.utilization == pytest.approx(1.5, rel=1e-12)
    assert over.utilization > 1.0
    assert not over.passed

    # A zero safety factor is infinite utilization, not a division error.
    assert ScorecardEntry.from_safety_factor("x", computed=0.0, required=1.5).utilization == float(
        "inf"
    )
    # A check that never ran has no utilization -- it must not read as a comfortable 0.
    assert ScorecardEntry.from_safety_factor("y", computed=None, required=1.5).utilization is None


def test_boundary_equal_to_required_passes():
    entry = ScorecardEntry.from_safety_factor("axial", computed=1.5, required=1.5)
    assert entry.status is CheckStatus.PASS


def test_missing_safety_factor_is_not_evaluated_not_a_silent_pass():
    # No silent green: an unavailable safety factor is NOT_EVALUATED, never PASS.
    entry = ScorecardEntry.from_safety_factor("fatigue", computed=None, required=2.0)
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert not entry.passed
    assert not entry.evaluated
    assert "not evaluated" in entry.detail


def test_entry_is_frozen_and_renders():
    entry = ScorecardEntry.from_safety_factor("torsion", computed=3.1, required=2.0)
    assert str(entry).startswith("[PASS] torsion:")
    assert entry.reference is None  # no clause by default


def test_entry_renders_its_code_reference():
    entry = ScorecardEntry.from_safety_factor("flexure", computed=2.0, required=1.5).model_copy(
        update={"reference": "AISC 360-16 Ch. F"}
    )
    assert entry.reference == "AISC 360-16 Ch. F"
    assert str(entry).endswith("[AISC 360-16 Ch. F]")


def _entry(name: str, status: CheckStatus) -> ScorecardEntry:
    return ScorecardEntry(name=name, status=status, detail="d")


def test_scorecard_passes_only_when_all_checks_pass():
    card = Scorecard(entries=(_entry("a", CheckStatus.PASS), _entry("b", CheckStatus.PASS)))
    assert card.status is CheckStatus.PASS
    assert card.passed
    assert card.failures() == ()
    assert card.not_evaluated() == ()


def test_scorecard_fails_if_any_check_fails():
    card = Scorecard(
        entries=(
            _entry("a", CheckStatus.PASS),
            _entry("b", CheckStatus.FAIL),
            _entry("c", CheckStatus.NOT_EVALUATED),
        )
    )
    # A failure dominates even when another check is unevaluated.
    assert card.status is CheckStatus.FAIL
    assert not card.passed
    assert [e.name for e in card.failures()] == ["b"]
    assert [e.name for e in card.not_evaluated()] == ["c"]


def test_scorecard_not_evaluated_blocks_a_pass_no_silent_green():
    # All non-failing but one unevaluated: not a pass.
    card = Scorecard(
        entries=(_entry("a", CheckStatus.PASS), _entry("b", CheckStatus.NOT_EVALUATED))
    )
    assert card.status is CheckStatus.NOT_EVALUATED
    assert not card.passed


def test_empty_scorecard_is_not_a_silent_pass():
    card = Scorecard()
    assert card.status is CheckStatus.NOT_EVALUATED
    assert not card.passed


# -- two-sided acceptance bands ------------------------------------------------


def test_over_margin_is_a_pass_with_a_warning_not_a_failure():
    # Target band 2.0-3.0, computed 8.7: passes the minimum but runs over the top.
    entry = ScorecardEntry.from_safety_factor("bracket", computed=8.7, required=2.0, upper=3.0)
    assert entry.status is CheckStatus.OVER_MARGIN
    assert entry.passed  # met the minimum — over-margin is not a failure
    assert entry.over_margin
    assert entry.evaluated
    assert "2.00" in entry.detail and "3.00" in entry.detail  # the band is stated
    assert "5.70" in entry.detail  # the excess is quantified (8.7 - 3.0)


def test_band_is_opt_in_high_margin_without_a_band_is_silent():
    # No upper declared: a high margin passes clean, no warning noise.
    entry = ScorecardEntry.from_safety_factor("bracket", computed=8.7, required=2.0)
    assert entry.status is CheckStatus.PASS
    assert not entry.over_margin


def test_within_band_upper_bound_is_a_clean_pass():
    at_top = ScorecardEntry.from_safety_factor("bracket", computed=3.0, required=2.0, upper=3.0)
    assert at_top.status is CheckStatus.PASS  # exactly at the top is still in band


def test_below_required_fails_even_with_a_band():
    entry = ScorecardEntry.from_safety_factor("bracket", computed=1.4, required=2.0, upper=3.0)
    assert entry.status is CheckStatus.FAIL


def test_scorecard_rolls_up_over_margin_without_blocking():
    card = Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor("a", computed=2.5, required=2.0),
            ScorecardEntry.from_safety_factor("b", computed=8.7, required=2.0, upper=3.0),
        )
    )
    assert card.status is CheckStatus.OVER_MARGIN
    assert card.passed  # over-margin never blocks export
    assert [e.name for e in card.over_margin()] == ["b"]


def test_a_failure_dominates_an_over_margin():
    card = Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor("a", computed=1.2, required=2.0),
            ScorecardEntry.from_safety_factor("b", computed=8.7, required=2.0, upper=3.0),
        )
    )
    assert card.status is CheckStatus.FAIL
    assert not card.passed


# -- typed repair hints --------------------------------------------------------


def test_repair_hint_only_rides_on_a_failing_check():
    hint = RepairHint.solved("D", direction=Direction.INCREASE, value=600.0, unit="mm")
    failed = ScorecardEntry.from_safety_factor(
        "sheave bending", computed=0.9, required=1.5, repair_hint=hint
    )
    assert failed.status is CheckStatus.FAIL
    assert failed.repair_hint is hint
    # A hint has no place on a passing check even if one is offered.
    passing = ScorecardEntry.from_safety_factor(
        "sheave bending", computed=2.0, required=1.5, repair_hint=hint
    )
    assert passing.repair_hint is None


def test_repair_hint_renders_direction_parameter_and_value():
    solved = RepairHint.solved("D", direction=Direction.INCREASE, value=612.5, unit="mm")
    assert str(solved) == "increase D to 612.5 mm"
    # A directional hint names the parameter and way, and omits an invented value.
    directional = RepairHint.directional("t", direction=Direction.INCREASE)
    assert directional.corrective_value is None
    assert str(directional) == "increase t"


def test_scorecard_collects_repair_hints_from_its_failures():
    card = Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor("a", computed=2.0, required=1.5),
            ScorecardEntry.from_safety_factor(
                "b",
                computed=0.8,
                required=1.5,
                repair_hint=RepairHint.directional("t", direction=Direction.INCREASE),
            ),
        )
    )
    hints = card.repair_hints()
    assert [h.parameter for h in hints] == ["t"]


def test_repair_hint_corrective_value_round_trips_through_the_inverse():
    # The hint's value must actually satisfy the forward check at the required
    # margin — a real design inverse, solved once, not searched.
    from anvilate.analysis.wire_rope import (
        minimum_sheave_diameter_for_bending_stress,
        wire_rope_bending_stress,
    )
    from anvilate.units import Quantity

    rope_modulus = Quantity(magnitude=83.0, unit="GPa")
    wire_diameter = Quantity(magnitude=1.2, unit="mm")
    allowable = Quantity(magnitude=300.0, unit="MPa")
    required_sf = 1.5

    def safety_factor(sheave: Quantity) -> float:
        stress = wire_rope_bending_stress(
            wire_diameter=wire_diameter,
            sheave_diameter=sheave,
            rope_modulus=rope_modulus,
        )
        return allowable.to("MPa").magnitude / stress.to("MPa").magnitude

    # An undersized sheave: bending stress too high, safety factor below 1.5.
    sf_small = safety_factor(Quantity(magnitude=250.0, unit="mm"))
    assert sf_small < required_sf

    # The inverse solves for the sheave diameter that just meets allowable/SF.
    derated = Quantity(magnitude=allowable.magnitude / required_sf, unit="MPa")
    d_fix = minimum_sheave_diameter_for_bending_stress(
        wire_diameter=wire_diameter,
        rope_modulus=rope_modulus,
        allowable_bending_stress=derated,
    )
    hint = RepairHint.solved(
        "sheave_diameter",
        direction=Direction.INCREASE,
        value=d_fix.to("mm").magnitude,
        unit="mm",
        provenance="minimum_sheave_diameter_for_bending_stress",
    )
    entry = ScorecardEntry.from_safety_factor(
        "sheave bending", computed=sf_small, required=required_sf, repair_hint=hint
    )
    assert entry.status is CheckStatus.FAIL

    # Applying the corrective value satisfies the check at exactly the margin.
    sf_fixed = safety_factor(Quantity(magnitude=hint.corrective_value, unit="mm"))
    assert sf_fixed >= required_sf
    assert abs(sf_fixed - required_sf) < 1e-6


# -- governing check identification and change ---------------------------------


def _sf(name: str, computed: float, required: float) -> ScorecardEntry:
    return ScorecardEntry.from_safety_factor(name, computed=computed, required=required)


def test_governing_is_the_tightest_utilization():
    card = Scorecard(
        entries=(
            _sf("bending", 3.0, 1.5),  # util 0.50
            _sf("bearing", 1.8, 1.5),  # util 0.83 — tightest
            _sf("shear", 4.0, 1.5),  # util 0.375
        )
    )
    assert card.governing().name == "bearing"


def test_governing_shift_names_previous_and_new():
    before = Scorecard(entries=(_sf("bending", 1.6, 1.5), _sf("bearing", 3.0, 1.5)))
    # A thicker flange relaxes bending; bearing now governs.
    after = Scorecard(entries=(_sf("bending", 3.2, 1.5), _sf("bearing", 1.7, 1.5)))
    shift = after.governing_shift(before)
    assert isinstance(shift, GoverningChange)
    assert shift.previous == "bending"
    assert shift.current == "bearing"
    assert "bending" in str(shift) and "bearing" in str(shift)


def test_governing_shift_is_none_when_the_same_check_still_governs():
    before = Scorecard(entries=(_sf("bending", 1.6, 1.5), _sf("bearing", 3.0, 1.5)))
    after = Scorecard(entries=(_sf("bending", 1.55, 1.5), _sf("bearing", 3.1, 1.5)))
    assert after.governing_shift(before) is None


def test_governing_shift_is_none_without_a_safety_factor_check():
    before = Scorecard(entries=(_entry("note", CheckStatus.PASS),))
    after = Scorecard(entries=(_sf("bending", 1.6, 1.5),))
    assert after.governing_shift(before) is None


# -- uncertainty annotation and fragility --------------------------------------


def _margin(shortfall: float):
    from anvilate.uncertainty import MarginUncertainty, Sensitivity

    return MarginUncertainty(
        samples=10000,
        seed=1,
        required=1.5,
        mean=1.7,
        std=0.3,
        shortfall_probability=shortfall,
        lower=1.3,
        upper=2.2,
        coverage=0.9,
        sensitivities=(Sensitivity(name="load", variance_share=1.0),),
    )


def test_fragile_flags_a_nominal_pass_with_a_material_shortfall():
    # A deterministic PASS whose attached distribution fails 20% of the time.
    entry = ScorecardEntry.from_safety_factor("bracket", computed=1.7, required=1.5).model_copy(
        update={"uncertainty": _margin(0.20)}
    )
    assert entry.status is CheckStatus.PASS  # deterministic verdict is unchanged
    assert entry.is_fragile()  # but flagged fragile under scatter
    assert not entry.is_fragile(threshold=0.5)  # threshold is configurable


def test_check_without_a_distribution_is_never_fragile():
    # No-op: a check with no attached distribution is never flagged.
    entry = ScorecardEntry.from_safety_factor("bracket", computed=1.7, required=1.5)
    assert entry.uncertainty is None
    assert not entry.is_fragile()


def test_scorecard_collects_fragile_checks_without_changing_status():
    card = Scorecard(
        entries=(
            _sf("solid", 3.0, 1.5),
            ScorecardEntry.from_safety_factor("fragile", computed=1.7, required=1.5).model_copy(
                update={"uncertainty": _margin(0.20)}
            ),
        )
    )
    # The deterministic roll-up still passes; fragility is a separate warning.
    assert card.status is CheckStatus.PASS
    assert card.passed
    assert [e.name for e in card.fragile()] == ["fragile"]
