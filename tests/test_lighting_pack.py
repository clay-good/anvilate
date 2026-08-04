"""Tests for the lighting pack: LightingInstallation and the illuminance-vs-LPD screen."""

from __future__ import annotations

from anvilate.packs.lighting import LightingInstallation, screen_lighting
from anvilate.scorecard import CheckStatus
from anvilate.units import Quantity


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


def _install(**overrides) -> LightingInstallation:
    fields = {
        "luminaire_count": 20,
        "lumens_per_luminaire": _q("3400 lumen"),
        "input_watts_per_luminaire": _q("30 W"),
        "coefficient_of_utilization": 0.62,
        "light_loss_factor": 0.8,
        "floor_area": _q("80 m**2"),
        "required_illuminance": _q("400 lux"),
        "allowable_power_density": _q("8.8 W/m**2"),
    }
    fields.update(overrides)
    return LightingInstallation(**fields)


def test_balanced_layout_passes_both_checks():
    card = screen_lighting(_install())
    assert card.status is CheckStatus.PASS
    names = {e.name: e for e in card.entries}
    assert set(names) == {"task illuminance", "lighting power density"}
    assert names["task illuminance"].status is CheckStatus.PASS
    assert names["lighting power density"].status is CheckStatus.PASS


def test_over_lit_layout_fails_the_energy_check():
    # More fixtures clear illuminance easily but push power density over the code cap.
    card = screen_lighting(_install(luminaire_count=28))
    assert card.status is CheckStatus.FAIL
    names = {e.name: e for e in card.entries}
    assert names["task illuminance"].status is CheckStatus.PASS
    assert names["lighting power density"].status is CheckStatus.FAIL


def test_under_lit_layout_fails_the_illuminance_check():
    # Fewer fixtures stay well under the energy cap but do not light the space enough.
    card = screen_lighting(_install(luminaire_count=14))
    assert card.status is CheckStatus.FAIL
    names = {e.name: e for e in card.entries}
    assert names["task illuminance"].status is CheckStatus.FAIL
    assert names["lighting power density"].status is CheckStatus.PASS


def test_references_cite_the_governing_standards():
    card = screen_lighting(_install())
    refs = " ".join(e.reference or "" for e in card.entries)
    assert "IES" in refs
    assert "ASHRAE 90.1" in refs
