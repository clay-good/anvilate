"""Tests for the geotechnical pack: ShallowFooting declaration and bearing screen."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from anvilate.packs.geotechnical import ShallowFooting, screen_shallow_footing
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
