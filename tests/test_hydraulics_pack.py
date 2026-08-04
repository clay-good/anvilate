"""Tests for the hydraulics pack: PumpDuty declaration and pump-selection screen."""

from __future__ import annotations

from anvilate.packs.hydraulics import (
    PipeRun,
    PumpDuty,
    screen_pipe_run,
    screen_pump_duty,
)
from anvilate.scorecard import CheckStatus
from anvilate.units import Quantity


def _q(text: str) -> Quantity:
    return Quantity.parse(text)


def _duty(**overrides) -> PumpDuty:
    fields = {
        "flow_rate": _q("0.05 m**3/s"),
        "total_head": _q("20 m"),
        "fluid_density": _q("1000 kg/m**3"),
        "efficiency": 0.70,
        "motor_rating": _q("18.5 kW"),
        "npsh_available": _q("5.6 m"),
        "npsh_required": _q("4 m"),
    }
    fields.update(overrides)
    return PumpDuty(**fields)


def test_pump_duty_sound_selection_passes():
    card = screen_pump_duty(_duty())
    assert card.status is CheckStatus.PASS
    names = {e.name: e for e in card.entries}
    assert set(names) == {"motor rating", "NPSH margin"}
    assert "safety factor 1.32" in names["motor rating"].detail
    assert all(e.reference is not None for e in card.entries)


def test_pump_duty_undersized_motor_and_low_npsh_fail():
    card = screen_pump_duty(_duty(motor_rating=_q("11 kW"), npsh_available=_q("4.2 m")))
    assert card.status is CheckStatus.FAIL
    assert {e.name for e in card.failures()} == {"motor rating", "NPSH margin"}


def test_pump_duty_low_npsh_alone_fails_only_that_check():
    card = screen_pump_duty(_duty(npsh_available=_q("4.2 m")))
    assert card.status is CheckStatus.FAIL
    assert {e.name for e in card.failures()} == {"NPSH margin"}


def _pipe(**overrides) -> PipeRun:
    fields = {
        "flow_rate": _q("0.05 m**3/s"),
        "diameter": _q("0.15 m"),
        "length": _q("100 m"),
        "roughness": _q("0.045 mm"),
        "fitting_loss_coefficient": 5.0,
        "kinematic_viscosity": _q("1e-6 m**2/s"),
        "available_head": _q("10 m"),
    }
    fields.update(overrides)
    return PipeRun(**fields)


def test_pipe_run_passes_with_enough_head_fails_without():
    ok = screen_pipe_run(_pipe())
    assert ok.status is CheckStatus.PASS
    (entry,) = ok.entries
    assert entry.name == "head budget"
    assert entry.reference is not None
    short = screen_pipe_run(_pipe(available_head=_q("5 m")))
    assert short.status is CheckStatus.FAIL
