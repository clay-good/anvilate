"""Tests for the masonry pack: MasonryWall declaration and TMS 402 stress screen."""

from __future__ import annotations

import pytest

from anvilate.packs.masonry import MasonryWall, screen_masonry_wall
from anvilate.scorecard import CheckStatus
from anvilate.units import Quantity


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


def _wall(**overrides) -> MasonryWall:
    fields = {
        "masonry_strength": _q("10 MPa"),
        "slenderness_ratio": 40.0,
        "axial_stress": _q("1.2 MPa"),
        "flexural_stress": _q("2.2 MPa"),
    }
    fields.update(overrides)
    return MasonryWall(**fields)


def test_masonry_wall_gravity_passes_but_combined_governs():
    card = screen_masonry_wall(_wall())
    # Axial (gravity) passes comfortably; the combined-with-wind check governs and fails.
    assert card.status is CheckStatus.FAIL
    names = {e.name: e for e in card.entries}
    assert set(names) == {"axial stress", "combined axial + flexure"}
    assert names["axial stress"].status is CheckStatus.PASS
    assert names["combined axial + flexure"].status is CheckStatus.FAIL
    assert all(e.reference is not None and "TMS 402" in e.reference for e in card.entries)

    # Absolute pins. The axial entry is PASS in BOTH masonry tests, so no test drove it to FAIL
    # and any upward scale on it was invisible to a verdict-only assertion. TMS 402 allowable
    # axial stress at f'm = 10 MPa, h/r = 40 is 0.25*10*(1 - (40/140)^2) = 2.29592 MPa.
    from anvilate.analysis import masonry_allowable_axial_stress

    allowable = masonry_allowable_axial_stress(
        masonry_strength=_q("10 MPa"), slenderness_ratio=40.0
    )
    assert allowable.to("MPa").magnitude == pytest.approx(2.295918367346939, rel=1e-9)
    assert names["axial stress"].safety_factor == pytest.approx(1.9132653061224492, rel=1e-9)
    assert names["combined axial + flexure"].safety_factor == pytest.approx(
        0.9885764499121266, rel=1e-9
    )


def test_masonry_wall_passes_when_wind_is_light():
    card = screen_masonry_wall(_wall(flexural_stress=_q("0.5 MPa")))
    assert card.status is CheckStatus.PASS
    assert card.passed


def test_the_default_required_safety_factor_is_the_tms_allowable_itself():
    # A mutation moving this default from 1.0 to 1.5 left the whole suite green: every
    # masonry case in the file sits either well above 1.5 or below 1.0, so no assertion
    # could see the move. The 1.0 is load-bearing — a TMS 402 allowable already carries its
    # own margin, and screening it at 1.5 would demand the margin twice.
    wall = _wall(axial_stress=_q("1.6 MPa"), flexural_stress=_q("0.7 MPa"))
    card = screen_masonry_wall(wall)
    names = {e.name: e for e in card.entries}
    # Both entries land strictly between 1.0 and 1.5, so the verdict itself pins the default.
    assert names["axial stress"].safety_factor == pytest.approx(1.4349, abs=0.001)
    assert names["combined axial + flexure"].safety_factor == pytest.approx(1.1731, abs=0.001)
    assert card.status is CheckStatus.PASS
    for entry in card.entries:
        assert entry.required_safety_factor == pytest.approx(1.0, rel=1e-12)
    # And the argument is honoured, not decorative.
    assert screen_masonry_wall(wall, required_safety_factor=1.5).status is CheckStatus.FAIL
