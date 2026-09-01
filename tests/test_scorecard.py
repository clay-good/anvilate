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


def test_a_nan_requirement_is_not_evaluated_rather_than_a_pass():
    # The isnan guard covered `computed` only. A NaN *requirement* makes both `computed <
    # required` and `computed > upper` False, so control fell to the PASS else-branch: a
    # check judged against an unknown minimum reported green.
    nan = float("nan")
    entry = ScorecardEntry.from_safety_factor("bending", computed=2.0, required=nan)
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert not entry.passed
    assert "NaN" in entry.detail
    # The computed number survives on the entry — it was the requirement that was unknown.
    assert entry.safety_factor == 2.0

    # Same trap on the upper band: a NaN upper silently disabled the OVER_MARGIN check.
    banded = ScorecardEntry.from_safety_factor("bending", computed=9.0, required=1.5, upper=nan)
    assert banded.status is CheckStatus.NOT_EVALUATED
    assert "upper" in banded.detail

    # An in-range call still answers normally — the guard did not swallow the good path.
    assert (
        ScorecardEntry.from_safety_factor("bending", computed=2.0, required=1.5).status
        is CheckStatus.PASS
    )
    assert (
        ScorecardEntry.from_safety_factor("bending", computed=9.0, required=1.5, upper=4.0).status
        is CheckStatus.OVER_MARGIN
    )


def test_a_failing_check_outranks_a_check_that_could_not_run():
    # The blocking precedence is FAIL > NOT_EVALUATED > PASS. Only the second half was
    # pinned; swapping the FAIL and NOT_EVALUATED ranks left the whole suite green, and
    # under that swap a card holding both points the reviewer at the gap instead of at the
    # thing that blocks.
    card = Scorecard(
        entries=(
            _entry("could not run", CheckStatus.NOT_EVALUATED),
            _entry("bolt shear", CheckStatus.FAIL),
        )
    )
    assert card.governing().name == "bolt shear"
    assert card.governing().status is CheckStatus.FAIL
    # And both still outrank a passing check carrying a real utilization.
    with_pass = Scorecard(
        entries=(_sf("bending", 1.51, 1.5), _entry("could not run", CheckStatus.NOT_EVALUATED))
    )
    assert with_pass.governing().name == "could not run"


def test_governing_shift_reports_a_move_off_a_check_carrying_no_safety_factor():
    # governing() is deliberately widened so a blocking check with no safety factor can
    # govern; governing_shift fed that same None into a `float` field and raised a
    # ValidationError on exactly the revision it exists to describe.
    before = Scorecard(
        entries=(_entry("floor deflection", CheckStatus.FAIL), _sf("bending", 2.0, 1.5))
    )
    after = Scorecard(
        entries=(_entry("floor deflection", CheckStatus.PASS), _sf("bending", 1.6, 1.5))
    )
    shift = after.governing_shift(before)
    assert isinstance(shift, GoverningChange)
    assert shift.previous == "floor deflection"
    assert shift.previous_utilization is None
    assert shift.current == "bending"
    assert shift.current_utilization == pytest.approx(1.5 / 1.6, rel=1e-9)
    # It renders without crashing, and says the absence out loud rather than printing 0.00.
    assert "util —" in str(shift)
    assert "util 0.94" in str(shift)

    # Symmetric case: the move is ONTO the factorless blocking check.
    back = before.governing_shift(after)
    assert back.current_utilization is None
    assert "util —" in str(back)


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


def test_a_nan_safety_factor_is_not_evaluated_rather_than_a_pass() -> None:
    """NaN compares False against everything, so it fell through to the PASS branch.

    ``from_safety_factor`` is the single funnel every screen in the library puts its
    float through, so one NaN upstream became a clean green anywhere -- and it did not
    even show up in ``not_evaluated()``, so nothing flagged the gap.
    """
    entry = ScorecardEntry.from_safety_factor("x", computed=float("nan"), required=2.0)
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert not entry.passed
    card = Scorecard(entries=(entry,))
    assert card.status is CheckStatus.NOT_EVALUATED
    assert [e.name for e in card.not_evaluated()] == ["x"]


def test_a_negative_safety_factor_governs_instead_of_ranking_below_every_pass() -> None:
    """utilization = required/computed went NEGATIVE for a negative safety factor.

    That ranked the worst check below every passing one, so ``governing()`` named a
    PASSING check as governing in a report whose overall status was FAIL -- pointing the
    reviewer at the wrong row. A zero factor was already treated as infinitely utilized;
    a negative one is strictly worse.
    """
    overstressed = ScorecardEntry.from_safety_factor("overstressed", computed=-0.5, required=2.0)
    fine = ScorecardEntry.from_safety_factor("fine", computed=3.0, required=2.0)
    assert overstressed.utilization == float("inf")
    assert Scorecard(entries=(overstressed, fine)).governing().name == "overstressed"
    # A zero factor keeps the behavior it already had, and ordinary ranking is untouched.
    assert ScorecardEntry.from_safety_factor("z", computed=0.0, required=2.0).utilization == float(
        "inf"
    )
    tight = ScorecardEntry.from_safety_factor("tight", computed=1.6, required=2.0)
    assert Scorecard(entries=(fine, tight)).governing().name == "tight"


def test_a_failing_check_without_a_safety_factor_still_governs() -> None:
    """governing() ranked only entries carrying a safety factor, and dropped the rest.

    A deflection or serviceability check is built as a bare entry with no safety factor,
    so its utilization is None and it fell out of the ranking entirely. A card could then
    FAIL on a beam 5x over its deflection limit and name a *passing* strength check as
    governing -- the same misdirection as the negative-safety-factor door above, through
    the wider of the two openings.
    """
    over = ScorecardEntry(
        name="deflection",
        status=CheckStatus.FAIL,
        detail="50.000 mm vs limit 10.000 mm",
    )
    fine = ScorecardEntry.from_safety_factor("bending", computed=3.0, required=1.5)
    card = Scorecard(entries=(over, fine))
    assert card.status is CheckStatus.FAIL
    assert over.utilization is None
    assert card.governing().name == "deflection"

    # A check that could not run outranks a pass for the same reason, and a card with
    # nothing blocking still ranks purely by utilization.
    unrun = ScorecardEntry(name="weld", status=CheckStatus.NOT_EVALUATED, detail="no throat given")
    assert Scorecard(entries=(unrun, fine)).governing().name == "weld"
    tight = ScorecardEntry.from_safety_factor("tight", computed=1.6, required=1.5)
    assert Scorecard(entries=(fine, tight)).governing().name == "tight"
    # Among failures, the one furthest past its limit still wins.
    worst = ScorecardEntry.from_safety_factor("worst", computed=0.2, required=1.5)
    assert Scorecard(entries=(over, worst)).governing().name == "worst"
    # Nothing blocking and no safety factor anywhere is still None.
    clean = ScorecardEntry(name="note", status=CheckStatus.PASS, detail="informational")
    assert Scorecard(entries=(clean,)).governing() is None


def test_an_unavailable_factor_keeps_both_the_requirement_and_the_band():
    """The ``computed is None`` branch used to drop both numbers, so a gap in an exported
    scorecard could not say what it would have been judged against. A test that pinned only
    the lower bound left the band half of the same regression free to come back: a
    not-evaluated banded check would export its minimum and silently lose its target."""
    entry = ScorecardEntry.from_safety_factor(
        "plate tear-out", computed=None, required=2.0, upper=4.0
    )
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert entry.required_safety_factor == pytest.approx(2.0)
    assert entry.upper_safety_factor == pytest.approx(4.0)
    # And it is still not a pass, and still carries no factor of its own.
    assert entry.passed is False
    assert entry.safety_factor is None


# --- The one-line rendering, which had no test at all ----------------------------------


def test_the_card_prints_the_two_facts_it_asks_a_reader_to_report():
    """`print(card)` is the lazy path, and it dropped half the answer.

    The rule for using a scorecard is "report `status` and `governing()`, not an impression
    of how the calculation went". The one-liner gave the first and not the second, so a
    reader doing the obvious thing learned that something failed and not which check to fix
    — the whole of what the card was assembled to tell them. Nothing asserted this string
    before, which is how it stayed half an answer.
    """
    card = Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor("net tension", computed=3.3, required=2.0),
            ScorecardEntry.from_safety_factor("pin bearing", computed=1.5, required=2.0),
        )
    )
    assert str(card) == "scorecard FAIL (2 checks); governing: pin bearing"


def test_a_passing_card_names_its_tightest_check_too():
    """On a pass the governing entry is the tightest one, which is the next question."""
    card = Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor("net tension", computed=3.3, required=2.0),
            ScorecardEntry.from_safety_factor("pin bearing", computed=2.1, required=2.0),
        )
    )
    assert str(card) == "scorecard PASS (2 checks); governing: pin bearing"


def test_a_check_that_could_not_run_is_counted_in_the_one_liner():
    """ "2 checks" over a card where one of them did not run is a true sentence that reads
    as a part screened twice."""
    card = Scorecard(
        entries=(
            ScorecardEntry(name="T0 geometry", status=CheckStatus.NOT_EVALUATED, detail="none"),
            ScorecardEntry.from_safety_factor("pin bearing", computed=2.1, required=2.0),
        )
    )
    rendered = str(card)
    assert rendered == "scorecard NOT_EVALUATED (2 checks, 1 not evaluated); governing: T0 geometry"


def test_an_empty_card_names_no_governing_check_rather_than_inventing_one():
    assert str(Scorecard()) == "scorecard NOT_EVALUATED (0 checks)"


def test_a_serialised_scorecard_carries_its_verdict():
    """The document a consumer receives used to be the checks and nothing else.

    `Scorecard.status` was a plain property, so `model_dump` dropped it — and the dump is
    what the attested `scorecard.json` artifact is, what the `scorecard` inside a signed
    predicate is, and what `anvilate check --format json` prints. A quality system, a
    verifier, and a CI job all got `{"entries": [...]}` and were left to rebuild the roll-up.

    **The roll-up is not a maximum**, which is what makes that dangerous rather than
    inconvenient. An *empty* card is NOT_EVALUATED; the obvious reimplementation — the worst
    status among the entries — has nothing to take a worst of and reports a pass over no
    checks. That is the silent green this library exists to refuse, produced by reading its
    own output.
    """
    import json

    from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry

    card = Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor("bending", computed=2.4, required=2.0),
            ScorecardEntry.from_safety_factor("bearing", computed=None, required=2.0),
        )
    )
    dumped = card.model_dump(mode="json")
    assert dumped["status"] == card.status.value == CheckStatus.NOT_EVALUATED.value
    assert json.loads(card.model_dump_json())["status"] == card.status.value

    # The case a consumer's own roll-up gets wrong, stated as a test rather than as prose.
    empty = Scorecard()
    assert empty.model_dump(mode="json") == {"entries": [], "status": "not_evaluated"}

    # Dump-only: a card read back from its own document is the same card, and `status` is
    # not something a caller can assert into a document that disagrees with its checks.
    assert Scorecard.model_validate(dumped) == card
    assert (
        Scorecard.model_validate({**dumped, "status": "pass"}).status is CheckStatus.NOT_EVALUATED
    )


def test_the_published_scorecard_contract_requires_the_verdict():
    """A schema that only describes `entries` describes a document with no verdict in it.

    Held against the released artifact rather than the live model: a client resolves the
    versioned URL, and that file is what it gets.
    """
    import json as json_module
    from pathlib import Path

    from anvilate.contracts import SCORECARD_SCHEMA_VERSION

    released = (
        Path(__file__).resolve().parent.parent
        / "docs"
        / "api"
        / "schemas"
        / "released"
        / f"scorecard-{SCORECARD_SCHEMA_VERSION}.json"
    )
    schema = json_module.loads(released.read_text(encoding="utf-8"))
    assert "status" in schema["properties"], "the published contract describes no verdict"
    assert "status" in schema.get("required", []), (
        "a verdict a document may omit is one a consumer has to cope with missing"
    )
    # And 1.0.0 stays what it was: a client pinned to it must not receive different content.
    old = released.with_name("scorecard-1.0.0.json")
    if old.exists():
        assert "status" not in json_module.loads(old.read_text())["properties"]


def test_a_failing_detail_never_prints_two_equal_numbers():
    """A FAIL whose own figures show no shortfall.

    At two fixed decimal places, a safety factor of 1.999 against a required 2.0 rendered as
    ``safety factor 2.00 vs required minimum 2.00`` — a blocking verdict contradicted by the
    numbers inside it, on the near-miss an engineer most needs to read correctly. The
    over-margin branch beside it had been widened for exactly this and the failing branch had
    not, so the fix written for one contradiction never reached the other.

    Swept across the boundary rather than spot-checked, because the defect only appears where
    the two figures are within half a printed place of each other.
    """
    import re

    from anvilate.scorecard import CheckStatus, ScorecardEntry

    printed = re.compile(r"safety factor (-?[\d.]+) vs required minimum (-?[\d.]+)")
    checked = 0
    for required in (1.0, 1.5, 1.67, 2.0, 2.5, 3.0):
        for delta in (-0.5, -1e-2, -1e-3, -1e-4, -1e-5, -1e-9, 0.0, 1e-9, 1e-3, 0.5):
            entry = ScorecardEntry.from_safety_factor(
                "bending", computed=required + delta, required=required
            )
            match = printed.search(entry.detail)
            if match is None:  # the over-margin branch writes a different sentence
                continue
            checked += 1
            shown, minimum = (float(group) for group in match.groups())
            failed = entry.status is CheckStatus.FAIL
            assert failed == (shown < minimum), (
                f"the card says {entry.status.value} and the line reads {entry.detail!r}, "
                "which is the opposite"
            )
    assert checked > 40, f"only {checked} details were rendered; the sweep found too few"

    # And the ordinary case keeps conventional precision: widening every line to nine places
    # to fix the near-miss would be a different rendering defect.
    ordinary = ScorecardEntry.from_safety_factor("bending", computed=1.5, required=2.0)
    assert ordinary.detail == "safety factor 1.50 vs required minimum 2.00"


def test_every_verdict_the_examples_print_agrees_with_its_own_numbers():
    """The same property over the rendered corpus rather than the renderer.

    490 examples print 217 lines that state a verdict beside the two numbers behind it. A
    line whose status and figures disagree is the failure this library exists to make
    impossible, at the surface a reader actually reads — and nothing had ever compared the
    two halves of one.
    """
    import io
    import re
    import runpy
    from contextlib import redirect_stdout
    from pathlib import Path

    shapes = (
        (True, re.compile(r"safety factor (-?[\d.]+) vs required minimum (-?[\d.]+)")),
        (True, re.compile(r"fundamental (-?[\d.]+) \S+ vs required minimum (-?[\d.]+)")),
        (False, re.compile(r"deflection (-?[\d.]+) \S+ vs limit (-?[\d.]+)")),
    )
    status = re.compile(r"\[(PASS|FAIL|OVER_MARGIN|NOT_EVALUATED)\]")

    examples = Path(__file__).resolve().parent.parent / "examples"
    checked, wrong = 0, []
    for path in sorted(examples.glob("*.py")):
        buffer = io.StringIO()
        try:
            with redirect_stdout(buffer):
                namespace = runpy.run_path(str(path))
                main = namespace.get("main")
                if callable(main):
                    main()
        except Exception:  # noqa: BLE001 - test_examples.py owns whether they run at all
            continue
        for line in buffer.getvalue().splitlines():
            verdict = status.search(line)
            if verdict is None:
                continue
            for at_least, pattern in shapes:
                found = pattern.search(line)
                if found is None:
                    continue
                left, right = (float(group) for group in found.groups())
                holds = left >= right if at_least else left <= right
                checked += 1
                if (verdict.group(1) in ("PASS", "OVER_MARGIN")) != holds:
                    wrong.append(f"{path.name}: {line.strip()}")

    assert checked > 150, f"only {checked} rendered verdicts were found across the examples"
    assert not wrong, "printed verdicts contradicted by their own figures:\n  " + "\n  ".join(
        wrong[:20]
    )
