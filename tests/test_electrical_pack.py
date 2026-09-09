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


def test_a_failing_feeder_solves_the_conductor_it_needs():
    """Two checks, two different levers — and the drop's lever can be out of reach.

    Ampacity moves with the conductor's rating; the drop moves with its area, but only
    through the RESISTIVE half. The reactance is the run's geometry and does not shrink,
    so the split has to be made before the solve, not after.
    """
    from anvilate.scorecard import Direction

    long_thin = _feeder(
        one_way_length=_q("220 m"),
        conductor_area=_q("16 mm**2"),
        conductor_ampacity=_q("45 A"),
    )
    card = screen_feeder(long_thin)
    hints = {e.name: e.repair_hint for e in card.entries}
    assert all(e.status is CheckStatus.FAIL for e in card.entries)
    assert hints["voltage drop"].parameter == "conductor_area"
    assert hints["conductor ampacity"].parameter == "conductor_ampacity"
    assert all(h.direction is Direction.INCREASE for h in hints.values())

    repaired = screen_feeder(
        _feeder(
            one_way_length=_q("220 m"),
            conductor_area=Quantity(magnitude=hints["voltage drop"].corrective_value, unit="mm**2"),
            conductor_ampacity=Quantity(
                magnitude=hints["conductor ampacity"].corrective_value, unit="A"
            ),
        )
    )
    assert all(e.status is CheckStatus.PASS for e in repaired.entries)
    for entry in repaired.entries:
        assert entry.safety_factor == pytest.approx(1.0, rel=1e-9)
        assert entry.repair_hint is None

    # With a reactance in the run the area has to grow FURTHER than the purely resistive
    # answer, because only part of the drop shrinks with it.
    with_reactance = screen_feeder(
        _feeder(
            one_way_length=_q("220 m"),
            conductor_area=_q("16 mm**2"),
            conductor_ampacity=_q("45 A"),
            reactance=_q("0.05 ohm"),
        )
    )
    reactive_hint = next(e.repair_hint for e in with_reactance.entries if e.name == "voltage drop")
    assert reactive_hint.corrective_value > hints["voltage drop"].corrective_value


def test_a_drop_the_reactance_alone_blows_gets_no_hint_at_all():
    """A lever that cannot reach is worse than silence.

    √3·I·X·sinφ does not shrink with the conductor, so on a reactive run it can exceed the
    whole allowance on its own. No conductor size fixes that — the answer is a different
    route, power-factor correction, or a higher distribution voltage — and the check says
    so by offering nothing rather than naming an area that would not work.
    """
    reactive = screen_feeder(
        _feeder(
            one_way_length=_q("220 m"),
            conductor_area=_q("16 mm**2"),
            conductor_ampacity=_q("45 A"),
            reactance=_q("0.4 ohm"),
        )
    )
    drop = next(e for e in reactive.entries if e.name == "voltage drop")
    assert drop.status is CheckStatus.FAIL
    assert drop.repair_hint is None
    # The ampacity check is untouched by the reactance and still names its lever, so the
    # silence above is about the drop and not about the card giving up.
    ampacity = next(e for e in reactive.entries if e.name == "conductor ampacity")
    assert ampacity.repair_hint is not None


def test_references_cite_the_nec():
    card = screen_feeder(_feeder())
    refs = " ".join(e.reference or "" for e in card.entries)
    assert "NEC" in refs
