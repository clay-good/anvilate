"""Duty-cycle fatigue: rainflow, a mean-stress correction, Basquin and Miner, by event.

Every figure is a hand calculation: N = (σ_a/a)^(1/b) on the curve a = 900 MPa,
b = −0.09, and Miner sums count/N per pass and occurrences × that per life.
"""

from __future__ import annotations

import pytest

from anvilate.analysis.duty_cycle import (
    BasquinCurve,
    DutyEvent,
    MeanStressCorrection,
    duty_cycle_damage,
)
from anvilate.refusal import RefusalError
from anvilate.units import Quantity

_CURVE = BasquinCurve(coefficient=Quantity(magnitude=900.0, unit="MPa"), exponent=-0.09,
                      source="illustrative steel S-N curve")  # fmt: skip


def _mpa(values) -> tuple[Quantity, ...]:
    return tuple(Quantity(magnitude=float(v), unit="MPa") for v in values)


def _life(amplitude: float) -> float:
    return (amplitude / 900.0) ** (1 / -0.09)


def _event(name, history, occurrences, repeating=True) -> DutyEvent:
    return DutyEvent(
        name=name,
        history=_mpa(history),
        occurrences_per_life=occurrences,
        source=f"{name} measured on the proving ground",
        repeating=repeating,
    )


def test_which_event_drives_life():
    """The spec's scenario: pothole, cornering and braking events."""
    events = [
        _event("pothole", (0, 400, -200, 0), 2_000),  # one big cycle, rarely
        _event("cornering", (0, 150, -150, 0), 200_000),  # moderate, often
        _event("braking", (0, 100, 0), 50_000),  # small, tensile-mean
    ]
    result = duty_cycle_damage(events, curve=_CURVE, correction=MeanStressCorrection.NONE)
    # pothole: repeating block 0, 400, −200 → one 600 MPa range, σa 300
    pothole = 2_000 / _life(300)
    # cornering: one 300 MPa range, σa 150; braking: one 100 MPa range, σa 50
    cornering = 200_000 / _life(150)
    braking = 50_000 / _life(50)
    total = pothole + cornering + braking
    assert result.total_damage == pytest.approx(total, rel=1e-12)
    shares = {e.event: e.share for e in result.events}
    assert shares["pothole"] == pytest.approx(pothole / total, rel=1e-12)
    assert (
        result.governing_event
        == max(
            ("pothole", pothole), ("cornering", cornering), ("braking", braking), key=lambda p: p[1]
        )[0]
    )
    assert sum(shares.values()) == pytest.approx(1.0)
    assert f"{result.governing_event} drives it" in str(result)


def test_goodman_inflates_a_tensile_mean_cycle():
    # one cycle 0 → 200: σa 100, σm 100; Goodman with Su 500: 100/(1 − 0.2) = 125
    event = _event("lift", (0, 200, 0), 1.0)
    result = duty_cycle_damage([event], curve=_CURVE, correction=MeanStressCorrection.GOODMAN,
                               ultimate_strength=Quantity(magnitude=500, unit="MPa"))  # fmt: skip
    # damage ~1e-15 per cycle: compare it scaled, or approx's default abs swamps the rel
    assert result.total_damage * _life(125) == pytest.approx(1.0, rel=1e-12)


def test_smith_watson_topper_uses_the_peak():
    # one cycle 0 → 200: σmax 200, σa 100 → √(200 × 100) = 141.42
    event = _event("lift", (0, 200, 0), 1.0)
    result = duty_cycle_damage([event], curve=_CURVE,
                               correction=MeanStressCorrection.SMITH_WATSON_TOPPER)  # fmt: skip
    assert result.total_damage * _life(20_000**0.5) == pytest.approx(1.0, rel=1e-12)


def test_a_wholly_compressive_cycle_does_no_damage_under_swt():
    event = _event("clamp", (0, -200, 0), 1.0)
    result = duty_cycle_damage([event], curve=_CURVE,
                               correction=MeanStressCorrection.SMITH_WATSON_TOPPER)  # fmt: skip
    assert result.total_damage == 0 and result.lives == float("inf")


def test_an_open_trace_reports_its_residual_and_damage_per_pass():
    """The spec's scenario: a measured trace applied once per pass."""
    trace = (-2, 1, -3, 5, -1, 3, -4, 4, -2)
    result = duty_cycle_damage([_event("road", [60 * x for x in trace], 10, repeating=False)],
                               curve=_CURVE, correction=MeanStressCorrection.NONE)  # fmt: skip
    (road,) = result.events
    assert road.count.residual == (300.0, -240.0, 240.0, -120.0)
    assert road.count.histogram()[0] == (540.0, 0.5)
    expected = sum(c.count / _life(c.range / 2) for c in road.count.cycles)
    assert road.damage_per_pass == pytest.approx(expected, rel=1e-12)
    assert road.damage_per_life == pytest.approx(10 * expected, rel=1e-12)


def test_a_history_of_fewer_than_three_reversals_is_refused_naming_its_event():
    with pytest.raises(RefusalError, match="'ramp'"):
        duty_cycle_damage([_event("ramp", (0, 100), 1, repeating=False)], curve=_CURVE,
                          correction=MeanStressCorrection.NONE)  # fmt: skip


def test_goodman_needs_the_ultimate():
    with pytest.raises(RefusalError, match="ultimate_strength"):
        duty_cycle_damage([_event("lift", (0, 200, 0), 1)], curve=_CURVE,
                          correction=MeanStressCorrection.GOODMAN)  # fmt: skip


def test_names_repeat_and_negative_occurrences_are_refused():
    with pytest.raises(RefusalError, match="repeat"):
        duty_cycle_damage([_event("a", (0, 1, 0), 1), _event("a", (0, 2, 0), 1)], curve=_CURVE,
                          correction=MeanStressCorrection.NONE)  # fmt: skip
    with pytest.raises(RefusalError, match="occurs -1"):
        duty_cycle_damage([_event("a", (0, 1, 0), -1)], curve=_CURVE,
                          correction=MeanStressCorrection.NONE)  # fmt: skip


def test_the_durability_page_quotes_the_example_it_points_to():
    from pathlib import Path

    page = (Path(__file__).parents[1] / "docs" / "durability-screening.md").read_text()
    assert "does 0.97 of the damage" in page and "4,000 times" in page
