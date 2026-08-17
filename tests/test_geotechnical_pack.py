"""Tests for the geotechnical pack: ShallowFooting declaration and bearing screen."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvilate.packs.geotechnical import (
    DrivenPile,
    InfiniteSlope,
    RetainingWall,
    ShallowFooting,
    screen_driven_pile,
    screen_infinite_slope,
    screen_retaining_wall,
    screen_shallow_footing,
)
from anvilate.scorecard import CheckStatus
from anvilate.units import Quantity


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


def _footing(**overrides) -> ShallowFooting:
    fields = {
        "width": _q("2.5 m"),
        "length": _q("2.5 m"),
        "embedment_depth": _q("1.5 m"),
        "applied_load": _q("5000 kN"),
        "friction_angle": 30.0,
        "cohesion": _q("25 kPa"),
        "unit_weight": _q("18 kN/m**3"),
    }
    fields.update(overrides)
    return ShallowFooting(**fields)


def test_shallow_footing_passes_at_service_load():
    card = screen_shallow_footing(_footing(), required_safety_factor=3.0)
    assert card.status is CheckStatus.PASS
    (entry,) = card.entries
    assert entry.name == "bearing capacity"
    assert entry.status is CheckStatus.PASS
    assert "safety factor 3.32" in entry.detail
    # The check cites the theory it implements (no silent green, and traceable).
    assert entry.reference is not None
    assert "Terzaghi" in entry.reference


def test_shallow_footing_fails_when_overloaded():
    card = screen_shallow_footing(_footing(applied_load=_q("7000 kN")), required_safety_factor=3.0)
    assert card.status is CheckStatus.FAIL
    assert not card.passed


def test_shallow_footing_rejects_inverted_plan():
    # width must be the shorter side.
    with pytest.raises(ValidationError):
        _footing(width=_q("3 m"), length=_q("2 m"))


def _wall(**overrides) -> RetainingWall:
    fields = {
        "retained_height": _q("4 m"),
        "backfill_unit_weight": _q("18 kN/m**3"),
        "backfill_friction_angle": 30.0,
        "vertical_load": _q("200 kN/m"),
        "load_arm": _q("1.6 m"),
        "base_friction_coefficient": 0.5,
    }
    fields.update(overrides)
    return RetainingWall(**fields)


def test_retaining_wall_passes_overturning_and_sliding():
    card = screen_retaining_wall(_wall())
    assert card.status is CheckStatus.PASS
    names = {e.name: e for e in card.entries}
    assert set(names) == {"overturning", "sliding"}
    assert "safety factor 5.00" in names["overturning"].detail
    assert "safety factor 2.08" in names["sliding"].detail
    assert all(e.reference is not None for e in card.entries)


def test_retaining_wall_underbuilt_fails_both():
    card = screen_retaining_wall(
        _wall(
            retained_height=_q("5 m"),
            backfill_friction_angle=28.0,
            vertical_load=_q("150 kN/m"),
            load_arm=_q("1.2 m"),
            base_friction_coefficient=0.45,
        )
    )
    assert card.status is CheckStatus.FAIL
    assert {e.name for e in card.failures()} == {"overturning", "sliding"}


def test_infinite_slope_dry_passes_saturated_fails():
    import math

    dry = InfiniteSlope(
        cohesion=_q("20 kPa"),
        friction_angle=30.0,
        unit_weight=_q("19 kN/m**3"),
        depth=_q("2.5 m"),
        slope_angle=35.0,
    )
    dry_card = screen_infinite_slope(dry)
    assert dry_card.status is CheckStatus.PASS
    (entry,) = dry_card.entries
    assert entry.name == "slope stability"
    assert entry.reference is not None
    # Add seepage pore pressure after rain; the same slope now fails.
    u = 9.81 * 2.5 * math.cos(math.radians(35)) ** 2
    wet = dry.model_copy(update={"pore_pressure": _q(f"{u} kPa")})
    assert screen_infinite_slope(wet).status is CheckStatus.FAIL


def _pile(**overrides) -> DrivenPile:
    fields = {
        "diameter": _q("0.4 m"),
        "length": _q("15 m"),
        "undrained_shear_strength": _q("75 kPa"),
        "adhesion_factor": 0.7,
        "applied_load": _q("350 kN"),
    }
    fields.update(overrides)
    return DrivenPile(**fields)


def test_driven_pile_passes_at_service_load_fails_when_overloaded():
    ok = screen_driven_pile(_pile())
    assert ok.status is CheckStatus.PASS
    (entry,) = ok.entries
    assert entry.name == "pile capacity"
    assert entry.reference is not None
    over = screen_driven_pile(_pile(applied_load=_q("500 kN")))
    assert over.status is CheckStatus.FAIL


# --- Repair hints: every declared lever round-trips, and the undeclarable ones stay silent.


def test_no_hint_rides_along_on_a_passing_check():
    """A passing check has nothing to repair, so it carries no hint — on every screen."""
    for card in (
        screen_shallow_footing(_footing()),
        screen_retaining_wall(_wall()),
        screen_driven_pile(_pile()),
    ):
        assert card.status is CheckStatus.PASS
        assert all(e.repair_hint is None for e in card.entries)


def test_retaining_wall_hints_the_weight_that_lands_both_margins():
    from anvilate.scorecard import Direction

    wall = _wall(
        retained_height=_q("5 m"),
        backfill_friction_angle=28.0,
        vertical_load=_q("150 kN/m"),
        load_arm=_q("1.2 m"),
        base_friction_coefficient=0.45,
    )
    card = screen_retaining_wall(wall)
    assert card.status is CheckStatus.FAIL
    for entry in card.failures():
        hint = entry.repair_hint
        assert hint is not None
        assert hint.parameter == "vertical_load"
        assert hint.direction is Direction.INCREASE
        assert hint.corrective_value is not None
        # Both factors are linear in V, so the solved weight lands the margin exactly —
        # one solve, not a search.
        repaired = screen_retaining_wall(
            wall.model_copy(update={"vertical_load": _q(f"{hint.corrective_value} kN/m")})
        )
        landed = next(e for e in repaired.entries if e.name == entry.name)
        assert landed.status is CheckStatus.PASS
        assert landed.safety_factor == pytest.approx(
            2.0 if entry.name == "overturning" else 1.5, rel=1e-9
        )


def test_driven_pile_hints_the_embedment_that_reaches_capacity():
    from anvilate.scorecard import Direction

    pile = _pile(applied_load=_q("500 kN"), length=_q("8 m"))
    (entry,) = screen_driven_pile(pile).entries
    assert entry.status is CheckStatus.FAIL
    hint = entry.repair_hint
    assert hint is not None
    assert (hint.parameter, hint.direction, hint.unit) == ("length", Direction.INCREASE, "m")
    assert hint.corrective_value is not None and hint.corrective_value > 8.0
    # End bearing does not move with L, so the shaft alone has to close the gap: the solve
    # is exact and lands at a demand ratio of 1.0.
    (landed,) = screen_driven_pile(
        pile.model_copy(update={"length": _q(f"{hint.corrective_value} m")})
    ).entries
    assert landed.status is CheckStatus.PASS
    assert landed.safety_factor == pytest.approx(1.0, rel=1e-9)


def test_shallow_footing_hints_a_direction_it_can_prove_but_no_value():
    from anvilate.scorecard import Direction

    footing = _footing(applied_load=_q("7000 kN"))
    (entry,) = screen_shallow_footing(footing).entries
    assert entry.status is CheckStatus.FAIL
    hint = entry.repair_hint
    assert hint is not None
    assert (hint.parameter, hint.direction) == ("width", Direction.INCREASE)
    # B enters q_ult through the shape and depth factors too, so there is no width to
    # solve for — and an invented number would be worse than a direction.
    assert hint.corrective_value is None
    # The direction it does declare is real: widening never lowers the factor.
    factors = []
    for width_m in (1.5, 1.8, 2.1, 2.5):  # D_f = 1.5 m, and the depth factors need D ≤ B
        (wider,) = screen_shallow_footing(
            footing.model_copy(update={"width": _q(f"{width_m} m")})
        ).entries
        factors.append(wider.safety_factor)
    assert factors == sorted(factors)


def test_infinite_slope_prefers_drainage_and_goes_silent_where_it_cannot_prove_a_lever():
    from anvilate.scorecard import Direction

    wet = InfiniteSlope(
        cohesion=_q("6 kPa"),
        friction_angle=28.0,
        unit_weight=_q("19 kN/m**3"),
        depth=_q("3 m"),
        slope_angle=20.0,
        pore_pressure=_q("30 kPa"),
    )
    (entry,) = screen_infinite_slope(wet).entries
    assert entry.status is CheckStatus.FAIL
    hint = entry.repair_hint
    assert hint is not None
    # FS is linear in u, so drainage is an exact solve — and it is the repair a slope
    # actually gets.
    assert (hint.parameter, hint.direction, hint.unit) == (
        "pore_pressure",
        Direction.DECREASE,
        "kPa",
    )
    (landed,) = screen_infinite_slope(
        wet.model_copy(update={"pore_pressure": _q(f"{hint.corrective_value} kPa")})
    ).entries
    assert landed.status is CheckStatus.PASS
    assert landed.safety_factor == pytest.approx(1.5, rel=1e-9)

    # A dry slope has no pore pressure to relieve; below 45° flattening is still provable,
    # so the hint is a direction with no value.
    dry = InfiniteSlope(
        cohesion=_q("0 kPa"),
        friction_angle=20.0,
        unit_weight=_q("19 kN/m**3"),
        depth=_q("3 m"),
        slope_angle=30.0,
    )
    (dry_entry,) = screen_infinite_slope(dry).entries
    assert dry_entry.status is CheckStatus.FAIL
    assert dry_entry.repair_hint is not None
    assert dry_entry.repair_hint.parameter == "slope_angle"
    assert dry_entry.repair_hint.direction is Direction.DECREASE
    assert dry_entry.repair_hint.corrective_value is None

    # Past 45° the declaration would be false — the driving term γ·z·sin(2β)/2 peaks there
    # and falls away, so FS turns back upward — and a hint is not offered at all.
    steep = dry.model_copy(update={"slope_angle": 50.0})
    (steep_entry,) = screen_infinite_slope(steep).entries
    assert steep_entry.status is CheckStatus.FAIL
    assert steep_entry.repair_hint is None


def test_the_slope_angle_reversal_the_hint_refuses_to_cross_is_real():
    """Guard on the guard: FS really does stop falling with β, and it stops near 45°."""
    slope = InfiniteSlope(
        cohesion=_q("5 kPa"),
        friction_angle=25.0,
        unit_weight=_q("18 kN/m**3"),
        depth=_q("2 m"),
        slope_angle=10.0,
    )

    def fs(angle: float) -> float:
        (entry,) = screen_infinite_slope(slope.model_copy(update={"slope_angle": angle})).entries
        return entry.safety_factor

    # Below the limit, every degree of steepening costs margin — the declared direction.
    below = [fs(a) for a in (5.0, 15.0, 25.0, 35.0, 44.0)]
    assert below == sorted(below, reverse=True)
    # Above it the trend reverses, which is exactly why no hint is offered there.
    assert fs(80.0) > fs(50.0)
