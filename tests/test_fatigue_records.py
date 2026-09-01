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
    EN1993_NORMAL_DETAIL_CATEGORIES,
    CurveSurvival,
    DatasetProvenance,
    FatigueCurve,
    FatigueRecord,
    FatigueSegment,
    LoadingMode,
    SpecimenGeometry,
    SpecimenMetadata,
    WeldDetailCategory,
    WeldStressKind,
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


def test_a_stress_concentration_factor_below_one_is_refused():
    """Kt is a *concentration*: the peak stress over the nominal, so it is at least 1.

    Below 1 the notch would be relieving stress rather than raising it, and a curve
    recorded against such a factor would read as more fatigue life than the specimen had.
    The refusal existed and nothing had run it; pinned by the boundary, since 1.0 is a
    smooth specimen and a real record rather than an error.
    """
    for below in (0.999, 0.5, 0.0, -1.0):
        with pytest.raises(ValidationError, match="stress concentration factor is at least 1"):
            _specimen(stress_concentration_factor=below)
    assert _specimen(stress_concentration_factor=1.0).stress_concentration_factor == 1.0
    assert _specimen(stress_concentration_factor=3.2).stress_concentration_factor == 3.2
    # And omitting it stays legal: an unrecorded factor is not a factor of one.
    assert _specimen().stress_concentration_factor is None


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


# --- A weld detail category is a record, not a number ---------------------------------


def _category(**kwargs) -> WeldDetailCategory:
    defaults = {
        "standard": "EN 1993-1-9",
        "edition": "2005",
        "table": "Table 8.4",
        "description": "transverse attachment, L <= 50 mm",
        "detail_category": Quantity.parse("80 MPa"),
    }
    return WeldDetailCategory(**{**defaults, **kwargs})


@pytest.mark.parametrize(
    ("field", "expected"),
    [
        # `standard` and `edition` are provenance fields, refused by the shared rule with
        # their own sentence; the other two by this model's own loop.
        ("standard", "the standard the detail category is read from"),
        ("edition", "the edition the detail category is read from"),
        ("table", "must state its table"),
        ("description", "must state its description"),
    ],
)
def test_a_detail_category_cannot_be_a_bare_number(field, expected):
    """The number is a curve label. Which standard drew the curve, and on what geometry,
    is what decides whether it applies to this weld."""
    with pytest.raises(ValidationError, match=expected):
        _category(**{field: "  "})


def test_the_en1993_ladder_is_discrete_and_a_value_between_rungs_is_refused():
    with pytest.raises(ValidationError, match="not an EN 1993-1-9 direct-stress"):
        _category(detail_category=Quantity.parse("85 MPa"))
    # The refusal names the near misses rather than leaving the caller to guess.
    with pytest.raises(ValidationError, match=r"\[80, 90\]"):
        _category(detail_category=Quantity.parse("85 MPa"))


def test_every_rung_of_the_published_ladder_is_accepted():
    assert len(EN1993_NORMAL_DETAIL_CATEGORIES) == 14, (
        "the ladder read off the published curve legend has fourteen rungs; a gate over "
        "an empty or truncated list would accept anything"
    )
    for value in EN1993_NORMAL_DETAIL_CATEGORIES:
        record = _category(detail_category=Quantity(magnitude=float(value), unit="MPa"))
        assert record.detail_category.to("MPa").magnitude == pytest.approx(value)


def test_another_standards_category_is_not_held_to_the_en1993_ladder():
    """IIW's FAT 85 exists and EN 1993-1-9's 85 does not. Declaring the standard is what
    makes the difference legible instead of a refusal the caller has to argue with."""
    record = _category(
        standard="IIW Recommendations",
        edition="2016",
        table="Table 3.2",
        detail_category=Quantity.parse("85 MPa"),
    )
    assert record.detail_category.to("MPa").magnitude == pytest.approx(85.0)


def test_the_records_curve_is_the_standards_curve():
    record = _category(detail_category=Quantity.parse("90 MPa"))
    expected = en1993_detail_category_curve(Quantity.parse("90 MPa"))
    assert record.curve().stress_range_at(2e6).to("MPa").magnitude == pytest.approx(
        expected.stress_range_at(2e6).to("MPa").magnitude, rel=1e-12
    )


def test_a_shear_category_refuses_the_direct_stress_curve():
    """Δτ_C = 100 and Δσ_C = 100 are the same label and different curves: the shear family
    runs at a single m = 5 with no knee at 5 million cycles."""
    shear = _category(
        table="Table 8.5",
        description="fillet weld, shear on the throat",
        detail_category=Quantity.parse("100 MPa"),
        stress_kind=WeldStressKind.SHEAR,
    )
    assert shear.detail_category.to("MPa").magnitude == pytest.approx(100.0)
    with pytest.raises(ValueError, match="single slope of m = 5"):
        shear.curve()
    # And a shear category is not held to the direct-stress ladder.
    assert (
        _category(
            detail_category=Quantity.parse("100 MPa"), stress_kind=WeldStressKind.SHEAR
        ).stress_kind
        is WeldStressKind.SHEAR
    )


def test_the_published_worked_endurance_is_reproduced():
    """SCI's worked example: detail category 160, a 250 MPa nominal range, N = 5.243e5."""
    from anvilate.analysis.fatigue import weld_detail_endurance_cycles

    cycles = weld_detail_endurance_cycles(
        stress_range=Quantity.parse("250 MPa"), detail_category=Quantity.parse("160 MPa")
    )
    assert cycles == pytest.approx(5.243e5, rel=1e-3)
