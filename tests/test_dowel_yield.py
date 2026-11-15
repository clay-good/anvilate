"""Dowel-type connections, against every value of AWC TR12's own Example 3.1.

The report publishes a worked bolted connection with three gap distances, three
grain-direction pairs and six yield modes — eighteen numbers per gap, fifty-four in all
— and the whole of this module is checked against them rather than against itself.

The reduction terms below are the example's own, from NDS Table 12.3.1B, and they are
here and not in the library on purpose: the NDS's tables are copyrighted and the module
reports the unreduced value ``P`` that TR12 computes. Three numbers in a test, used to
reproduce a published worked example, is what "the caller supplies the reduction term
with its citation" looks like from the inside.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvilate.analysis.dowel_yield import (
    DOUBLE_SHEAR_MODES,
    TR12_CITATION,
    DowelConnection,
    DowelYield,
    ModeCapacity,
    ShearPlanes,
    YieldMode,
    dowel_bearing_strength,
    dowel_yield_capacity,
    hankinson_bearing_strength,
)
from anvilate.refusal import RefusalError
from anvilate.units import Quantity

_Q = Quantity.parse

# TR12 Example 3.1: a wood-to-wood single-shear bolted connection.
DIAMETER = _Q("0.5 inch")
BENDING_YIELD = _Q("45000 psi")
THICKNESS = _Q("1.5 inch")
PARALLEL = _Q("4800 psi")
PERPENDICULAR = _Q("2550 psi")

#: NDS Table 12.3.1B, as TR12 Example 3.1 applies it: 4 for the bearing modes, 3.6 for
#: mode II, 3.2 for the hinge modes, each times Kθ = 1 + 0.25·(θ/90). The example's three
#: rows are parallel/parallel (θ = 0), parallel/perpendicular and perpendicular/
#: perpendicular (θ = 90 for both).
_BASE_REDUCTION = {
    YieldMode.IM: 4.0,
    YieldMode.IS: 4.0,
    YieldMode.II: 3.6,
    YieldMode.IIIM: 3.2,
    YieldMode.IIIS: 3.2,
    YieldMode.IV: 3.2,
}

#: Every published value of Example 3.1: (gap, main, side) -> {mode: P5%/Rd}.
_PUBLISHED: dict[tuple[float, str, str], dict[YieldMode, int]] = {
    (0.0, "parallel", "parallel"): {
        YieldMode.IM: 900,
        YieldMode.IS: 900,
        YieldMode.II: 414,
        YieldMode.IIIM: 550,
        YieldMode.IIIS: 550,
        YieldMode.IV: 663,
    },  # fmt: skip
    (0.0, "parallel", "perpendicular"): {
        YieldMode.IM: 720,
        YieldMode.IS: 383,
        YieldMode.II: 250,
        YieldMode.IIIM: 380,
        YieldMode.IIIS: 324,
        YieldMode.IV: 442,
    },  # fmt: skip
    (0.0, "perpendicular", "perpendicular"): {
        YieldMode.IM: 383,
        YieldMode.IS: 383,
        YieldMode.II: 176,
        YieldMode.IIIM: 289,
        YieldMode.IIIS: 289,
        YieldMode.IV: 387,
    },  # fmt: skip
    (0.25, "parallel", "parallel"): {
        YieldMode.IM: 900,
        YieldMode.IS: 900,
        YieldMode.II: 370,
        YieldMode.IIIM: 482,
        YieldMode.IIIS: 482,
        YieldMode.IV: 576,
    },  # fmt: skip
    (0.25, "parallel", "perpendicular"): {
        YieldMode.IM: 720,
        YieldMode.IS: 383,
        YieldMode.II: 224,
        YieldMode.IIIM: 341,
        YieldMode.IIIS: 284,
        YieldMode.IV: 393,
    },  # fmt: skip
    (0.25, "perpendicular", "perpendicular"): {
        YieldMode.IM: 383,
        YieldMode.IS: 383,
        YieldMode.II: 157,
        YieldMode.IIIM: 258,
        YieldMode.IIIS: 258,
        YieldMode.IV: 349,
    },  # fmt: skip
    (0.5, "parallel", "parallel"): {
        YieldMode.IM: 900,
        YieldMode.IS: 900,
        YieldMode.II: 333,
        YieldMode.IIIM: 426,
        YieldMode.IIIS: 426,
        YieldMode.IV: 501,
    },  # fmt: skip
    (0.5, "parallel", "perpendicular"): {
        YieldMode.IM: 720,
        YieldMode.IS: 383,
        YieldMode.II: 202,
        YieldMode.IIIM: 307,
        YieldMode.IIIS: 250,
        YieldMode.IV: 350,
    },  # fmt: skip
    (0.5, "perpendicular", "perpendicular"): {
        YieldMode.IM: 383,
        YieldMode.IS: 383,
        YieldMode.II: 142,
        YieldMode.IIIM: 231,
        YieldMode.IIIS: 231,
        YieldMode.IV: 315,
    },  # fmt: skip
}


def _strength(direction: str) -> Quantity:
    return PARALLEL if direction == "parallel" else PERPENDICULAR


def _reduction(main: str, side: str) -> dict[YieldMode, float]:
    """Rd = base × Kθ, with θ the largest load-to-grain angle in the connection."""
    theta = 0.0 if (main, side) == ("parallel", "parallel") else 90.0
    k_theta = 1.0 + 0.25 * (theta / 90.0)
    return {mode: base * k_theta for mode, base in _BASE_REDUCTION.items()}


def _connection(gap: float, main: str, side: str, **overrides: object) -> DowelConnection:
    fields: dict[str, object] = {
        "diameter": DIAMETER,
        "bending_yield_strength": BENDING_YIELD,
        "main_bearing_length": THICKNESS,
        "side_bearing_length": THICKNESS,
        "main_bearing_strength": _strength(main),
        "side_bearing_strength": _strength(side),
        "gap": Quantity(magnitude=gap, unit="inch") if gap else None,
    }
    fields.update(overrides)
    return DowelConnection(**fields)  # type: ignore[arg-type]


# --- the golden case ------------------------------------------------------------------


@pytest.mark.parametrize("case", sorted(_PUBLISHED))
def test_every_value_of_tr12_example_3_1_is_reproduced(case):
    """Fifty-four published numbers, re-derived rather than trusted."""
    gap, main, side = case
    result = dowel_yield_capacity(_connection(gap, main, side))
    reduction = _reduction(main, side)
    for mode, published in _PUBLISHED[case].items():
        entry = result.of(mode)
        assert entry.capacity is not None, mode
        ours = entry.capacity.to("lbf").magnitude / reduction[mode]
        # The report rounds to the pound, so half a pound is the whole tolerance.
        assert ours == pytest.approx(published, abs=0.55), f"{case} {mode.value}"


@pytest.mark.parametrize("case", sorted(_PUBLISHED))
def test_the_governing_mode_is_the_one_the_report_underlines(case):
    """Z is the minimum of P/Rd across the modes, and the report's own Z column is it.

    The minimum is taken **after** the reduction, so a module reporting the smallest
    unreduced P would name the wrong mode wherever the terms differ — which they do,
    between mode II at 3.6 and the hinge modes at 3.2.
    """
    gap, main, side = case
    result = dowel_yield_capacity(_connection(gap, main, side))
    reduction = _reduction(main, side)
    reduced = {
        mode: result.of(mode).capacity.to("lbf").magnitude / reduction[mode] for mode in YieldMode
    }
    assert min(reduced, key=lambda mode: reduced[mode]) is YieldMode.II
    assert min(reduced.values()) == pytest.approx(min(_PUBLISHED[case].values()), abs=0.55)


def test_a_gap_costs_capacity_and_the_clause_most_engineers_use_has_no_term_for_it():
    """TR12's reason for existing: a quarter inch of gap is about a tenth of the value."""
    none, quarter, half = (
        dowel_yield_capacity(_connection(gap, "parallel", "parallel")).capacity
        for gap in (0.0, 0.25, 0.5)
    )
    assert none.magnitude > quarter.magnitude > half.magnitude
    assert quarter.magnitude / none.magnitude == pytest.approx(370 / 414, rel=2e-3)


# --- the sign the table hides ----------------------------------------------------------


def test_the_quadratics_root_is_the_negative_b_one():
    """The one thing a reader of Table 1-1 gets wrong, and it does not look like an error.

    With `+B` the mode II value of the first published row comes out near 2,414 instead
    of 414 — a number large enough to pass for a capacity. This pins the published one.
    """
    from math import sqrt

    resistance = PARALLEL.to("psi").magnitude * DIAMETER.to("inch").magnitude
    length = THICKNESS.to("inch").magnitude
    a = 1.0 / (4.0 * resistance) + 1.0 / (4.0 * resistance)
    b = length
    c = -2.0 * resistance * length * length / 4.0
    wrong = (b + sqrt(b * b - 4 * a * c)) / (2 * a)
    right = (-b + sqrt(b * b - 4 * a * c)) / (2 * a)

    ours = dowel_yield_capacity(_connection(0.0, "parallel", "parallel"))
    mode_two = ours.of(YieldMode.II).capacity.to("lbf").magnitude
    assert mode_two == pytest.approx(right, rel=1e-12)
    assert mode_two != pytest.approx(wrong, rel=0.5)
    assert wrong / right > 5.0


# --- double shear -----------------------------------------------------------------------


def test_two_modes_do_not_apply_in_double_shear_and_say_why():
    """TR12 Table 1-1 footnote 1. A list that included them would govern on a mechanism
    the connection cannot reach."""
    result = dowel_yield_capacity(
        _connection(0.0, "parallel", "parallel", shear_planes=ShearPlanes.DOUBLE)
    )
    for mode in (YieldMode.II, YieldMode.IIIM):
        entry = result.of(mode)
        assert entry.capacity is None
        assert "symmetric about its main member" in entry.not_applicable
        assert "does not apply" in str(entry)
    assert {m for m in YieldMode if result.of(m).capacity is not None} == DOUBLE_SHEAR_MODES
    assert result.governing.mode in DOUBLE_SHEAR_MODES


def test_double_shear_doubles_the_side_member_bearing_and_not_the_main():
    """Two side members carry the load and one main member does."""
    single = dowel_yield_capacity(_connection(0.0, "parallel", "parallel"))
    double = dowel_yield_capacity(
        _connection(0.0, "parallel", "parallel", shear_planes=ShearPlanes.DOUBLE)
    )
    assert double.of(YieldMode.IS).capacity.to("lbf").magnitude == pytest.approx(
        2 * single.of(YieldMode.IS).capacity.to("lbf").magnitude, rel=1e-12
    )
    assert double.of(YieldMode.IM).capacity == single.of(YieldMode.IM).capacity


# --- the bearing strengths --------------------------------------------------------------


def test_the_bearing_formulas_are_the_three_the_appendix_states():
    """11,200 G parallel, 6,100 G^1.45/√D perpendicular, 16,600 G^1.84 below a quarter inch."""
    half = _Q("0.5 inch")
    assert dowel_bearing_strength(specific_gravity=0.5, diameter=half).to(
        "psi"
    ).magnitude == pytest.approx(5600.0)  # the Appendix's own worked value
    assert dowel_bearing_strength(specific_gravity=0.5, diameter=half, perpendicular=True).to(
        "psi"
    ).magnitude == pytest.approx(6100 * 0.5**1.45 / 0.5**0.5, rel=1e-12)
    small = _Q("0.131 inch")
    assert dowel_bearing_strength(specific_gravity=0.5, diameter=small).to(
        "psi"
    ).magnitude == pytest.approx(16600 * 0.5**1.84, rel=1e-12)
    # Below the quarter inch the formula has no direction, so the flag changes nothing.
    assert dowel_bearing_strength(
        specific_gravity=0.5, diameter=small, perpendicular=True
    ) == dowel_bearing_strength(specific_gravity=0.5, diameter=small)


def test_the_quarter_inch_boundary_belongs_to_the_larger_formula():
    """A quarter inch exactly is `D ≥ ¼″`, so it is 11,200 G and not 16,600 G^1.84."""
    at = dowel_bearing_strength(specific_gravity=0.5, diameter=_Q("0.25 inch"))
    assert at.to("psi").magnitude == pytest.approx(5600.0)
    under = dowel_bearing_strength(specific_gravity=0.5, diameter=_Q("0.249 inch"))
    assert under.to("psi").magnitude == pytest.approx(16600 * 0.5**1.84, rel=1e-12)


def test_hankinson_returns_each_end_at_its_own_angle_and_between_in_between():
    ends = {
        0.0: PARALLEL.to("psi").magnitude,
        90.0: PERPENDICULAR.to("psi").magnitude,
    }
    for degrees, expected in ends.items():
        value = hankinson_bearing_strength(
            parallel=PARALLEL,
            perpendicular=PERPENDICULAR,
            angle=Quantity(magnitude=degrees, unit="degree"),
        )
        assert value.to("psi").magnitude == pytest.approx(expected, rel=1e-12)
    middle = (
        hankinson_bearing_strength(
            parallel=PARALLEL, perpendicular=PERPENDICULAR, angle=_Q("45 degree")
        )
        .to("psi")
        .magnitude
    )
    assert ends[90.0] < middle < ends[0.0]
    # The harmonic mean at 45 degrees, which is what the formula reduces to there.
    assert middle == pytest.approx(2 * ends[0.0] * ends[90.0] / (ends[0.0] + ends[90.0]), rel=1e-12)


def test_an_angle_past_ninety_is_refused_because_the_formula_reflects():
    with pytest.raises(RefusalError, match="a caller writing 120 means 60"):
        hankinson_bearing_strength(
            parallel=PARALLEL, perpendicular=PERPENDICULAR, angle=_Q("120 degree")
        )


def test_a_specific_gravity_outside_what_wood_has_is_refused():
    with pytest.raises(RefusalError, match="between 0 and 1.5"):
        dowel_bearing_strength(specific_gravity=0.0, diameter=_Q("0.5 inch"))
    with pytest.raises(RefusalError, match="between 0 and 1.5"):
        dowel_bearing_strength(specific_gravity=2.0, diameter=_Q("0.5 inch"))


# --- what the declaration refuses --------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "wrong"),
    [
        ("diameter", _Q("0.5 psi")),
        ("main_bearing_length", _Q("1 kN")),
        ("bending_yield_strength", _Q("45000 N")),
        ("main_bearing_strength", _Q("4800 mm")),
    ],
)
def test_a_dimension_that_is_not_what_it_says_is_refused(field, wrong):
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match=field):
        _connection(0.0, "parallel", "parallel", **{field: wrong})


def test_a_negative_gap_is_two_members_overlapping_and_is_refused():
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="not negative"):
        DowelConnection(
            diameter=DIAMETER,
            bending_yield_strength=BENDING_YIELD,
            main_bearing_length=THICKNESS,
            side_bearing_length=THICKNESS,
            main_bearing_strength=PARALLEL,
            side_bearing_strength=PARALLEL,
            gap=_Q("-1 mm"),
        )


def test_a_mode_states_a_capacity_or_a_reason_and_never_both_or_neither():
    from pydantic import ValidationError

    with pytest.raises(ValidationError, match="neither a capacity nor a reason"):
        ModeCapacity(mode=YieldMode.IV)
    with pytest.raises(ValidationError, match="both a capacity and a reason"):
        ModeCapacity(mode=YieldMode.IV, capacity=_Q("100 lbf"), not_applicable="no")
    with pytest.raises(ValidationError, match="positive finite force"):
        ModeCapacity(mode=YieldMode.IV, capacity=Quantity(magnitude=0.0, unit="lbf"))


def test_a_result_states_all_six_modes_or_is_refused():
    """A mode left out reads as one that did not govern, not one nobody computed."""
    from pydantic import ValidationError

    full = dowel_yield_capacity(_connection(0.0, "parallel", "parallel"))
    with pytest.raises(ValidationError, match="all six"):
        DowelYield(modes=full.modes[:4])
    with pytest.raises(ValidationError, match="all six"):
        DowelYield(modes=(*full.modes, full.modes[0]))
    with pytest.raises(ValidationError, match="no yield mode applies"):
        DowelYield(
            modes=tuple(
                ModeCapacity(mode=mode, not_applicable="nothing here") for mode in YieldMode
            )
        )


def test_the_solver_takes_a_connection_and_says_so_otherwise():
    with pytest.raises(RefusalError, match="connection is a DowelConnection"):
        dowel_yield_capacity({"diameter": "0.5 inch"})  # type: ignore[arg-type]


def test_every_rendering_says_what_it_is_about():
    connection = _connection(0.25, "parallel", "perpendicular")
    assert "0.5 in dowel in single shear" in str(connection)
    assert "0.25 inch gap" in str(connection)
    result = dowel_yield_capacity(connection)
    rendered = str(result)
    assert "by mode" in rendered
    assert TR12_CITATION in rendered
    assert "unreduced" in rendered
    assert result.citation == TR12_CITATION
    assert all(mode.description for mode in YieldMode)
    assert "crushes" in str(result.of(YieldMode.IM))


def test_a_non_finite_diameter_cannot_reach_a_formula_that_ignores_it():
    """The parallel-to-grain formula is 11,200 G, and the diameter is not in it.

    A NaN diameter met only `<` comparisons, every one of which is False against a NaN,
    so the guards passed it through; it then selected the branch that never reads it and
    came back as an ordinary 5,600 psi. Nothing downstream could tell that number from a
    real one. The finiteness check is what closes it, and it has to be a check of its own
    because no bound can see a NaN.
    """
    for bad in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(RefusalError, match="diameter is a finite"):
            dowel_bearing_strength(
                specific_gravity=0.50, diameter=Quantity(magnitude=bad, unit="inch")
            )


def test_a_non_finite_bearing_strength_is_refused_rather_than_propagated():
    """The Hankinson formula does carry a NaN out, but a refusal names the parameter."""
    good = Quantity.parse("2550 psi")
    for name in ("parallel", "perpendicular"):
        for bad in (float("nan"), float("inf")):
            arguments = {"parallel": good, "perpendicular": good, "angle": Quantity.parse("30 deg")}
            arguments[name] = Quantity(magnitude=bad, unit="psi")
            with pytest.raises(RefusalError, match=f"{name} is a finite"):
                hankinson_bearing_strength(**arguments)


@pytest.mark.parametrize(
    "field",
    [
        "diameter",
        "bending_yield_strength",
        "main_bearing_length",
        "side_bearing_length",
        "main_bearing_strength",
        "side_bearing_strength",
        "gap",
    ],
)
def test_no_field_of_a_connection_takes_a_non_finite_value(field):
    """`dowel_yield_capacity` takes a model, so its refusals are the model's.

    The binder in `tests/test_fraction_guards.py` cannot construct a `DowelConnection`,
    which puts this function outside the package-wide non-finite probe. This is the test
    that stands in for it, field by field, so the exemption is backed rather than assumed.
    """
    unit = "inch" if "length" in field or field in ("diameter", "gap") else "psi"
    for bad in (float("nan"), float("inf"), float("-inf")):
        arguments = {
            "diameter": Quantity.parse("0.75 inch"),
            "bending_yield_strength": Quantity.parse("45000 psi"),
            "main_bearing_length": Quantity.parse("3.5 inch"),
            "side_bearing_length": Quantity.parse("1.5 inch"),
            "main_bearing_strength": Quantity.parse("5600 psi"),
            "side_bearing_strength": Quantity.parse("5600 psi"),
        }
        arguments[field] = Quantity(magnitude=bad, unit=unit)
        with pytest.raises(ValidationError):
            DowelConnection(**arguments)


def test_the_direction_flag_is_a_bool_and_not_a_truthy_thing():
    """`perpendicular="no"` is truthy, and would have returned the perpendicular value."""
    for bad in ("no", None, [], float("nan"), 0.0):
        with pytest.raises(RefusalError, match="perpendicular is True or False"):
            dowel_bearing_strength(
                specific_gravity=0.50, diameter=Quantity.parse("0.75 inch"), perpendicular=bad
            )
