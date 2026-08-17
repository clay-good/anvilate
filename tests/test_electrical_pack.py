"""Tests for the electrical pack: Feeder declaration and the NEC drop/ampacity screen."""

from __future__ import annotations

import pytest

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

    # Absolute pins, not just verdicts. Verdict-only assertions left the whole voltage-drop chain
    # scalable -- even the percent conversion could be wrong by half -- because the PASS cases
    # only get safer under an inflated factor and the FAIL case fails too hard to be rescued.
    # I = 37000/(sqrt(3)*480*0.85) = 52.358 A, dV = 3.700 V, drop = 0.7708%, 3%/0.7708% = 3.8919.
    assert names["voltage drop"].safety_factor == pytest.approx(3.891891891891891, rel=1e-9)
    assert names["conductor ampacity"].safety_factor == pytest.approx(2.1964276727332894, rel=1e-9)


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
