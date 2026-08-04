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
    assert "safety factor 3.33" in entry.detail
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
