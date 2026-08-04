"""Tests for the ventilation pack: VentilationZone and the ASHRAE 62.1 / air-change screen."""

from __future__ import annotations

from anvilate.packs.ventilation import VentilationZone, screen_ventilation
from anvilate.scorecard import CheckStatus
from anvilate.units import Quantity


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


def _zone(**overrides) -> VentilationZone:
    fields = {
        "people_outdoor_rate": _q("5 ft**3/min"),
        "occupancy": 50.0,
        "area_outdoor_rate": _q("0.06 ft**3/min/ft**2"),
        "floor_area": _q("5000 ft**2"),
        "zone_air_distribution_effectiveness": 0.8,
        "provided_outdoor_airflow": _q("800 ft**3/min"),
        "room_volume": _q("50000 ft**3"),
        "required_air_changes": 0.5,
    }
    fields.update(overrides)
    return VentilationZone(**fields)


def test_adequate_zone_passes_both_checks():
    card = screen_ventilation(_zone())
    assert card.status is CheckStatus.PASS
    names = {e.name: e for e in card.entries}
    assert set(names) == {"outdoor air", "air changes per hour"}
    assert all(e.status is CheckStatus.PASS for e in card.entries)


def test_low_outdoor_air_fails_the_ashrae_check():
    # 600 cfm is below the ~688 cfm ASHRAE 62.1 requirement (Voz = 550/0.8).
    card = screen_ventilation(_zone(provided_outdoor_airflow=_q("600 ft**3/min")))
    assert card.status is CheckStatus.FAIL
    names = {e.name: e for e in card.entries}
    assert names["outdoor air"].status is CheckStatus.FAIL
    assert names["air changes per hour"].status is CheckStatus.PASS


def test_high_air_change_demand_fails_despite_adequate_outdoor_air():
    # The same 800 cfm meets the outdoor-air rate but cannot make 2 ACH in a 50,000 ft^3 room.
    card = screen_ventilation(_zone(required_air_changes=2.0))
    assert card.status is CheckStatus.FAIL
    names = {e.name: e for e in card.entries}
    assert names["outdoor air"].status is CheckStatus.PASS
    assert names["air changes per hour"].status is CheckStatus.FAIL


def test_references_cite_the_governing_basis():
    card = screen_ventilation(_zone())
    refs = " ".join(e.reference or "" for e in card.entries)
    assert "ASHRAE 62.1" in refs
