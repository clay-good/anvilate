"""The fatigue-record schema, anchored against a curve whose answers are known independently.

The load-bearing test here is the first one. `anvilate.analysis.fatigue` computes the
EN 1993-1-9 curve straight from the standard's two branches; `en1993_detail_category_curve`
expresses the same curve in this schema. They share no code, so agreeing at every decade is
evidence the schema's arithmetic is right, in a way that a fixture written alongside the
schema could never be.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvilate.analysis.fatigue import weld_detail_allowable_stress_range
from anvilate.standards.fatigue import (
    CurveSurvival,
    DatasetProvenance,
    FatigueCurve,
    FatigueRecord,
    FatigueSegment,
    LoadingMode,
    SpecimenGeometry,
    SpecimenMetadata,
    en1993_detail_category_curve,
)
from anvilate.units import Quantity


def _q(magnitude: float, unit: str) -> Quantity:
    return Quantity(magnitude=magnitude, unit=unit)


@pytest.mark.parametrize("detail_category", [36.0, 71.0, 90.0, 160.0])
@pytest.mark.parametrize(
    "cycles", [1.0e4, 5.0e4, 1.0e5, 1.0e6, 2.0e6, 4.9e6, 5.0e6, 1.0e7, 5.0e7, 1.0e8]
)
def test_the_schema_reproduces_the_standards_curve_computed_independently(detail_category, cycles):
    category = _q(detail_category, "MPa")
    through_the_schema = en1993_detail_category_curve(category).stress_range_at(cycles)
    from_the_standard = weld_detail_allowable_stress_range(
        life_cycles=cycles, detail_category=category
    )
    assert through_the_schema is not None
    assert through_the_schema.to("MPa").magnitude == pytest.approx(
        from_the_standard.to("MPa").magnitude, rel=1e-12
    )


def test_past_the_cutoff_the_curve_flattens_rather_than_continuing_down():
    curve = en1993_detail_category_curve(_q(90.0, "MPa"))
    at_cutoff = curve.stress_range_at(1.0e8)
    beyond = curve.stress_range_at(1.0e10)
    assert at_cutoff is not None and beyond is not None
    assert beyond.to("MPa").magnitude == pytest.approx(at_cutoff.to("MPa").magnitude)


def test_below_the_methods_scope_the_curve_declines_and_the_bare_formula_does_not():
    """A deliberate difference between the schema and the formula, asserted as deliberate.

    `weld_detail_allowable_stress_range` is the standard's arithmetic and will evaluate at
    any positive N. The record carries the standard's *scope* as well as its arithmetic:
    below about 10,000 cycles the nominal-stress method does not apply, and the honest
    answer is no answer rather than a number off the end of the method.
    """
    category = _q(90.0, "MPa")
    assert en1993_detail_category_curve(category).stress_range_at(1.0e3) is None
    # The formula still answers there, which is what makes the scope a real addition.
    assert weld_detail_allowable_stress_range(life_cycles=1.0e3, detail_category=category)


@pytest.mark.parametrize("cycles", [0.0, -1.0, float("nan"), float("inf")])
def test_a_nonsense_life_gets_no_answer(cycles):
    # `<= 0` is False for NaN, so the finiteness half of the guard is doing work.
    assert en1993_detail_category_curve(_q(90.0, "MPa")).stress_range_at(cycles) is None


def _segment(**overrides) -> dict:
    base = {
        "slope": 3.0,
        "reference_stress_range": _q(90.0, "MPa"),
        "reference_cycles": 2.0e6,
        "max_cycles": 5.0e6,
    }
    base.update(overrides)
    return base


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("slope", 0.0, "slope"),
        ("slope", float("nan"), "slope"),
        ("reference_stress_range", _q(0.0, "MPa"), "positive"),
        ("reference_stress_range", _q(float("nan"), "MPa"), "positive"),
        ("reference_stress_range", _q(90.0, "mm"), "must be a stress"),
        ("reference_cycles", float("inf"), "reference_cycles"),
        ("max_cycles", -1.0, "max_cycles"),
    ],
)
def test_a_segment_that_cannot_describe_a_curve_is_refused(field, value, message):
    with pytest.raises(ValidationError, match=message):
        FatigueSegment(**_segment(**{field: value}))


def test_a_curve_that_jumps_at_its_breakpoint_is_refused():
    """Two branches that disagree where they meet are two curves.

    Which one answers a query then depends on which side of a float comparison the target
    life lands on, which is not a property an allowable should have.
    """
    high = FatigueSegment(**_segment())
    discontinuous = FatigueSegment(
        slope=5.0,
        # The continuous value here is 66.31 MPa; 80 is a step up at the breakpoint.
        reference_stress_range=_q(80.0, "MPa"),
        reference_cycles=5.0e6,
        max_cycles=1.0e8,
    )
    with pytest.raises(ValidationError, match="jumps at"):
        FatigueCurve(
            survival=CurveSurvival.P97_7,
            segments=(high, discontinuous),
            min_cycles=1.0e4,
        )


def test_segments_that_do_not_advance_are_refused():
    segment = FatigueSegment(**_segment())
    with pytest.raises(ValidationError, match="ascending order"):
        FatigueCurve(survival=CurveSurvival.P97_7, segments=(segment, segment), min_cycles=1.0e4)


def test_a_cutoff_above_the_end_of_the_curve_is_refused():
    segment = FatigueSegment(**_segment())
    with pytest.raises(ValidationError, match="not a step up"):
        FatigueCurve(
            survival=CurveSurvival.P97_7,
            segments=(segment,),
            min_cycles=1.0e4,
            cutoff_stress_range=_q(200.0, "MPa"),
        )


def test_an_empty_curve_is_refused():
    with pytest.raises(ValidationError, match="at least one segment"):
        FatigueCurve(survival=CurveSurvival.P97_7, segments=(), min_cycles=1.0e4)


def _specimen(**overrides) -> SpecimenMetadata:
    base = {
        "material": "S355",
        "geometry": SpecimenGeometry.WELDED_JOINT,
        "loading_mode": LoadingMode.AXIAL,
        "environment": "laboratory air",
        "temperature": _q(20.0, "degC"),
        "stress_ratio_independent": True,
    }
    base.update(overrides)
    return SpecimenMetadata(**base)


def test_a_curve_with_no_stress_ratio_is_refused():
    with pytest.raises(ValidationError, match="stress ratio"):
        _specimen(stress_ratio_independent=False)


def test_a_curve_cannot_be_both_r_independent_and_carry_an_r():
    with pytest.raises(ValidationError, match="One of the two is wrong"):
        _specimen(stress_ratio_independent=True, stress_ratio=0.1)


def test_a_plain_specimen_curve_carries_its_r():
    specimen = _specimen(
        geometry=SpecimenGeometry.POLISHED,
        loading_mode=LoadingMode.ROTATING_BENDING,
        stress_ratio_independent=False,
        stress_ratio=-1.0,
    )
    assert specimen.stress_ratio == -1.0


def test_a_dataset_nobody_can_retrieve_is_refused():
    with pytest.raises(ValidationError, match="doi or a url"):
        DatasetProvenance(
            dataset="somebody's spreadsheet",
            version="1",
            license="CC-BY-4.0",
            retrieved="2026-08-25",
        )


def _record(curve: FatigueCurve | None = None) -> FatigueRecord:
    return FatigueRecord(
        name="S355 transverse butt weld, as-welded",
        curve=curve or en1993_detail_category_curve(_q(90.0, "MPa")),
        specimen=_specimen(),
        provenance=DatasetProvenance(
            dataset="example welded-joint S-N dataset",
            version="1.0.0",
            license="CC-BY-4.0",
            retrieved="2026-08-25",
            doi="10.0000/example",
            specimen_count=142,
        ),
    )


def test_a_mean_curve_does_not_answer_a_request_for_a_design_curve():
    """The reason `survival` is required rather than optional.

    Fatigue scatter is wide enough that a mean curve read as a design curve overstates
    life by roughly a factor of two at the same stress range. Returning the mean value
    with a caveat somewhere would be the silent version of that.
    """
    mean = en1993_detail_category_curve(_q(90.0, "MPa")).model_copy(
        update={"survival": CurveSurvival.MEAN}
    )
    record = _record(mean)
    assert record.allowable_stress_range(cycles=2.0e6, required_survival=CurveSurvival.MEAN)
    assert (
        record.allowable_stress_range(cycles=2.0e6, required_survival=CurveSurvival.P97_7) is None
    )


def test_a_design_curve_answers_a_request_for_a_mean_one():
    # The ordering runs one way: more conservative satisfies less conservative.
    record = _record()
    assert record.allowable_stress_range(cycles=2.0e6, required_survival=CurveSurvival.MEAN)
    assert record.allowable_stress_range(cycles=2.0e6, required_survival=CurveSurvival.P95)


def test_the_two_ways_a_record_declines_are_different_and_both_return_none():
    record = _record()
    # Out of scope on life.
    assert (
        record.allowable_stress_range(cycles=1.0e3, required_survival=CurveSurvival.P97_7) is None
    )
    # In scope on life, and the answer is a number — so the None above is the scope, not a
    # record that never answers anything.
    assert record.allowable_stress_range(cycles=1.0e6, required_survival=CurveSurvival.P97_7)


def test_a_record_needs_all_four_of_its_parts():
    # There is no "just the curve" constructor: pydantic refuses the record outright.
    with pytest.raises(ValidationError):
        FatigueRecord(name="x", curve=en1993_detail_category_curve(_q(90.0, "MPa")))


def test_a_copy_cannot_smuggle_past_the_continuity_check():
    """model_copy runs no after-validator, so the class overrides it.

    Without the override, `curve.model_copy(update={"segments": ...})` builds exactly the
    discontinuous curve the constructor refuses — one call away from the only check that
    can catch two branches disagreeing.
    """
    curve = en1993_detail_category_curve(_q(90.0, "MPa"))
    discontinuous = (
        curve.segments[0],
        FatigueSegment(
            slope=5.0,
            reference_stress_range=_q(80.0, "MPa"),
            reference_cycles=5.0e6,
            max_cycles=1.0e8,
        ),
    )
    with pytest.raises(ValidationError, match="jumps at"):
        curve.model_copy(update={"segments": discontinuous})
    # And an ordinary copy still works, so the override did not break copying.
    assert curve.model_copy(update={"survival": CurveSurvival.MEAN}).survival is CurveSurvival.MEAN


@pytest.mark.parametrize("cutoff", [float("nan"), 0.0, -5.0])
def test_a_cutoff_that_is_not_a_positive_finite_stress_is_refused(cutoff):
    """All three walked past the step-up check, and each one poisons the curve differently.

    NaN because `cutoff > last` is False for NaN — the curve then answers NaN past its last
    segment, and a NaN stress range compares False against every limit it meets, so the
    check that consumes it passes. Zero and negative because they are *plausible* rather
    than absurd: a cutoff of zero says every stress range survives forever, which is an
    infinite fatigue life reported as an ordinary allowable.
    """
    segment = FatigueSegment(**_segment())
    with pytest.raises(ValidationError, match="positive finite stress"):
        FatigueCurve(
            survival=CurveSurvival.P97_7,
            segments=(segment,),
            min_cycles=1.0e4,
            cutoff_stress_range=_q(cutoff, "MPa"),
        )
