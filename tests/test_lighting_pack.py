"""Tests for the lighting pack: LightingInstallation and the illuminance-vs-LPD screen."""

from __future__ import annotations

import pytest

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


def test_the_light_loss_factor_actually_reaches_the_lumen_method():
    """The number, not the verdict — the LLF could be dropped and every test still passed.

    All three scenario tests above assert only a :class:`CheckStatus`, and the margins are
    wide enough on both sides that deleting the light-loss factor from the lumen method
    (inflating illuminance by 1/0.8 = 25%) moved no verdict. A maintained illuminance is
    E = N·F·CU·LLF/A, so the safety factor against the requirement is linear in LLF: this
    pins it at two values and asserts the ratio is exactly the ratio of the factors.
    """
    balanced = {e.name: e for e in screen_lighting(_install()).entries}["task illuminance"]
    # 20 x 3400 lm x 0.62 x 0.80 / 80 m² = 421.6 lux against 400 required.
    assert balanced.safety_factor == pytest.approx(421.6 / 400.0, rel=1e-6)
    brighter = {e.name: e for e in screen_lighting(_install(light_loss_factor=1.0)).entries}
    assert brighter["task illuminance"].safety_factor == pytest.approx(
        balanced.safety_factor / 0.8, rel=1e-9
    )
    # And the under-lit case, which is the one that would have hidden the deletion: it fails
    # at 0.74 and would still fail at 0.93 with the factor gone.
    under = {e.name: e for e in screen_lighting(_install(luminaire_count=14)).entries}
    assert under["task illuminance"].safety_factor == pytest.approx(295.12 / 400.0, rel=1e-4)


def test_the_power_density_check_pins_its_own_number():
    entries = {e.name: e for e in screen_lighting(_install()).entries}
    # 20 x 30 W / 80 m² = 7.5 W/m² against the 8.8 W/m² cap.
    assert entries["lighting power density"].safety_factor == pytest.approx(8.8 / 7.5, rel=1e-6)
