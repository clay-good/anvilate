"""Tests for the electrical pack: Feeder declaration and the NEC drop/ampacity screen."""

from __future__ import annotations

from anvilate.packs.electrical import Feeder, screen_feeder
from anvilate.scorecard import CheckStatus
from anvilate.units import Quantity


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


def _feeder(**overrides) -> Feeder:
    fields = {
        "load_power": _q("37 kW"),
        "power_factor": 0.85,
        "line_voltage": _q("480 V"),
        "resistivity": _q("1.68e-8 ohm*m"),
        "one_way_length": _q("100 m"),
        "conductor_area": _q("35 mm**2"),
        "conductor_ampacity": _q("115 A"),
    }
    fields.update(overrides)
    return Feeder(**fields)


def test_adequate_feeder_passes_both_checks():
    card = screen_feeder(_feeder())
    assert card.status is CheckStatus.PASS
    names = {e.name: e for e in card.entries}
    assert set(names) == {"voltage drop", "conductor ampacity"}
    assert all(e.status is CheckStatus.PASS for e in card.entries)


def test_long_thin_run_fails_on_voltage_drop_not_ampacity():
    card = screen_feeder(
        _feeder(
            one_way_length=_q("300 m"), conductor_area=_q("16 mm**2"), conductor_ampacity=_q("65 A")
        )
    )
    assert card.status is CheckStatus.FAIL
    names = {e.name: e for e in card.entries}
    assert names["voltage drop"].status is CheckStatus.FAIL
    assert names["conductor ampacity"].status is CheckStatus.PASS


def test_undersized_conductor_fails_on_ampacity_not_drop():
    card = screen_feeder(
        _feeder(
            one_way_length=_q("30 m"), conductor_area=_q("6 mm**2"), conductor_ampacity=_q("40 A")
        )
    )
    assert card.status is CheckStatus.FAIL
    names = {e.name: e for e in card.entries}
    assert names["conductor ampacity"].status is CheckStatus.FAIL
    assert names["voltage drop"].status is CheckStatus.PASS


def test_references_cite_the_nec():
    card = screen_feeder(_feeder())
    refs = " ".join(e.reference or "" for e in card.entries)
    assert "NEC" in refs
