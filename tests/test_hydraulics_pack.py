"""Tests for the hydraulics pack: PumpDuty declaration and pump-selection screen."""

from __future__ import annotations

import pytest

from anvilate.analysis import darcy_friction_factor
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

    # Absolute pin. The relative-roughness term reaches the friction factor through Colebrook,
    # which is barely sensitive to eps/D in this turbulent regime -- inflating eps/D five-fold
    # only moves the factor from 1.5268 to 1.2298, still a PASS. A verdict-only test therefore
    # left that line free, and it is exactly the line that invites reading mm as m.
    # v = 2.8294 m/s, Re = 424413, eps/D = 3.0e-4, f = 0.016569, losses 6.5495 m of 10 m.
    assert entry.safety_factor == pytest.approx(1.5268255805433, rel=1e-9)
    assert darcy_friction_factor(reynolds=424413.1815993, relative_roughness=3.0e-4) == (
        pytest.approx(0.016568958219220213, rel=1e-9)
    )
    # The units slip this guards against: roughness in metres rather than millimetres is a 1000x
    # error on eps/D and turns the PASS into a hard FAIL, which the pin above catches.
    slipped = screen_pipe_run(_pipe(roughness=_q("0.045 m")))
    assert slipped.entries[0].safety_factor == pytest.approx(0.16887957550413993, rel=1e-9)
    assert slipped.status is CheckStatus.FAIL


def test_the_two_required_margins_are_pinned_not_merely_implied():
    """Both defaults could be moved anywhere in (1.05, 1.40) and no test noticed.

    The scenario tests assert the NPSH verdict and only the *computed* motor safety factor,
    never the required one — so the 1.1 NPSH cushion, which is the cited engineering
    criterion the check exists for, was unpinned. These assert the required factors
    directly, and assert that raising them moves the verdict.
    """
    card = screen_pump_duty(_duty())
    entries = {e.name: e for e in card.entries}
    npsh = next(e for name, e in entries.items() if "npsh" in name.lower())
    motor = next(e for name, e in entries.items() if "motor" in name.lower())
    assert npsh.required_safety_factor == pytest.approx(1.1)
    assert motor.required_safety_factor == pytest.approx(1.0)
    # And they are live: a requirement above the computed factor flips the verdict.
    tightened = screen_pump_duty(_duty(), npsh_margin_factor=10.0, motor_service_factor=10.0)
    assert all(e.status is CheckStatus.FAIL for e in tightened.entries)


def test_every_hydraulics_entry_shows_the_work_it_did():
    """The three checks render a worked calculation, and it is the one they performed.

    A derivation is only worth carrying if its substituted line reproduces the number the
    verdict rests on. These assert both halves: that no symbol is left standing where a
    value belongs, and that the result agrees with the safety factor the entry reports —
    so a derivation that drifted away from its own check fails here rather than shipping a
    plausible formula beside an unrelated verdict.
    """
    entries = list(screen_pump_duty(_duty()).entries) + list(screen_pipe_run(_pipe()).entries)
    assert len(entries) == 3

    for entry in entries:
        assert entry.derivation is not None, f"{entry.name} carries no derivation"
        assert entry.derivation.unresolved_symbols() == ()
        assert entry.derivation.citation == entry.reference

    worked = {entry.name: entry.derivation for entry in entries}

    # P_s = ρ·g·Q·H/η = 1000 · 9.80665 · 0.05 · 20 / 0.70 = 14.010 kW, and the motor is
    # 18.5 kW — which is the 1.3205 safety factor the entry reports.
    shaft = worked["motor rating"].result.value.to("kW").magnitude
    assert shaft == pytest.approx(14.0095, rel=1e-5)
    assert 18.5 / shaft == pytest.approx(
        next(e for e in entries if e.name == "motor rating").safety_factor, rel=1e-12
    )

    # The suction margin is a subtraction, so it is checked against the ratio the verdict
    # uses rather than restated: 5.6 − 4 = 1.6 m in hand on a 4 m requirement.
    npsh = worked["NPSH margin"]
    assert npsh.result.value.to("m").magnitude == pytest.approx(1.6, rel=1e-12)
    assert "5.600 m − 4.000 m" in npsh.substituted()

    # h_L = (f·L/D + ΣK)·v²/2g. The pinned friction factor above gives 6.5495 m against
    # the 10 m available, and the head-budget entry divides exactly those two.
    losses = worked["head budget"].result.value.to("m").magnitude
    assert losses == pytest.approx(6.5495, rel=1e-4)
    assert 10.0 / losses == pytest.approx(
        next(e for e in entries if e.name == "head budget").safety_factor, rel=1e-12
    )
