"""Modal separation and drop screening, held to hand work and to energy balance.

The drop's peak deceleration is checked by an independent route: the contact spring
absorbs the landing energy, ½·k·x² = ½·m·v², so x = v·√(m/k) and a = k·x/m. The pulse
length is half the contact's period, π·√(m/k).
"""

from __future__ import annotations

from math import pi, sqrt

import pytest

from anvilate.analysis.durability import (
    ExcitationBand,
    MountedItem,
    drop_screen,
    modal_separation,
)
from anvilate.analysis.dynamics import half_sine_shock_amplification
from anvilate.refusal import RefusalError
from anvilate.units import Quantity


def _hz(v: float) -> Quantity:
    return Quantity(magnitude=v, unit="Hz")


_MOTOR = ExcitationBand(name="motor 2nd order", low=_hz(380), high=_hz(450),
                        source="drive spec DS-12 §4")  # fmt: skip


def test_a_mount_inside_the_motor_order_band_fails():
    """The spec's scenario: a 410 Hz first mode inside a 380–450 Hz band."""
    (result,) = modal_separation(modes=[("mount 1st", _hz(410))], bands=[_MOTOR],
                                 required_ratio=1.25, ceiling=_hz(2000))  # fmt: skip
    assert not result.passes and result.ratio == 1.0
    assert "mount 1st at 410 Hz vs 'motor 2nd order'" in str(result)
    assert "required 1.25" in str(result)


@pytest.mark.parametrize(("f", "ratio", "passes"), [(600.0, 600 / 450, True),
                                                    (540.0, 1.2, False),
                                                    (300.0, 380 / 300, True)])  # fmt: skip
def test_separation_is_measured_from_the_nearer_edge(f, ratio, passes):
    (result,) = modal_separation(modes=[("m", _hz(f))], bands=[_MOTOR], required_ratio=1.25,
                                 ceiling=_hz(2000))  # fmt: skip
    assert result.ratio == pytest.approx(ratio, rel=1e-12) and result.passes is passes


def test_modes_above_the_ceiling_are_out_of_scope():
    results = modal_separation(modes=[("low", _hz(100)), ("high", _hz(3000))], bands=[_MOTOR],
                               required_ratio=1.25, ceiling=_hz(2000))  # fmt: skip
    assert [r.mode for r in results] == ["low"]


def test_a_handheld_dropped_from_1_2_m():
    """The spec's scenario: 0.4 kg from 1.2 m, a board mount inside."""
    k = 5.0e5  # N/m, the caller's contact stiffness
    board = MountedItem(name="board mount", mass=Quantity(magnitude=0.05, unit="kg"),
                        natural_frequency=_hz(300))  # fmt: skip
    screen = drop_screen(mass=Quantity(magnitude=0.4, unit="kg"),
                         height=Quantity(magnitude=1.2, unit="m"),
                         contact_stiffness=Quantity(magnitude=k, unit="N/m"),
                         items=[board])  # fmt: skip
    v = sqrt(2 * 9.80665 * 1.2)  # 4.8513 m/s
    assert screen.impact_velocity == pytest.approx(v, rel=1e-12)
    assert screen.energy == pytest.approx(0.4 * 9.80665 * 1.2, rel=1e-12)  # 4.707 J
    # energy balance: x = v √(m/k), a = k x / m
    x = v * sqrt(0.4 / k)
    assert screen.peak_deceleration_g * 9.80665 == pytest.approx(k * x / 0.4, rel=1e-12)
    assert screen.pulse_duration == pytest.approx(pi * sqrt(0.4 / k), rel=1e-12)  # 2.81 ms
    (load,) = screen.items
    expected_a = half_sine_shock_amplification(
        pulse_duration=Quantity(magnitude=screen.pulse_duration, unit="s"),
        natural_frequency=_hz(300),
    )
    assert load.amplification == pytest.approx(expected_a, rel=1e-12)
    assert load.load == pytest.approx(0.05 * k * x / 0.4 * expected_a, rel=1e-12)
    assert screen.estimated and "estimated peak" in str(screen)


def test_a_rigid_item_feels_the_pulse_itself():
    battery_item = MountedItem(name="battery", mass=Quantity(magnitude=0.2, unit="kg"))
    screen = drop_screen(mass=Quantity(magnitude=1.0, unit="kg"),
                         height=Quantity(magnitude=0.5, unit="m"),
                         contact_stiffness=Quantity(magnitude=1e5, unit="N/m"),
                         items=[battery_item])  # fmt: skip
    (battery,) = screen.items
    assert battery.amplification == 1.0
    assert battery.peak_acceleration_g == pytest.approx(screen.peak_deceleration_g, rel=1e-12)


def test_a_stiffer_surface_shortens_the_pulse_and_raises_the_peak():
    def screen(k):
        return drop_screen(mass=Quantity(magnitude=0.4, unit="kg"),
                           height=Quantity(magnitude=1.2, unit="m"),
                           contact_stiffness=Quantity(magnitude=k, unit="N/m"))  # fmt: skip

    soft, hard = screen(1e5), screen(4e5)
    assert hard.peak_deceleration_g == pytest.approx(2 * soft.peak_deceleration_g, rel=1e-12)
    assert hard.pulse_duration == pytest.approx(soft.pulse_duration / 2, rel=1e-12)


def test_refusals():
    with pytest.raises(RefusalError, match="required_ratio"):
        modal_separation(modes=[("m", _hz(10))], bands=[_MOTOR], required_ratio=0.9,
                         ceiling=_hz(100))  # fmt: skip
    with pytest.raises(RefusalError, match="no excitation band"):
        modal_separation(modes=[("m", _hz(10))], bands=[], required_ratio=1.2, ceiling=_hz(100))
    backwards = ExcitationBand(name="x", low=_hz(500), high=_hz(400), source="s")
    with pytest.raises(RefusalError, match="high"):
        modal_separation(modes=[("m", _hz(10))], bands=[backwards], required_ratio=1.2,
                         ceiling=_hz(100))  # fmt: skip
    with pytest.raises(ValueError, match="height"):
        drop_screen(mass=Quantity(magnitude=1, unit="kg"),
                    height=Quantity(magnitude=float("nan"), unit="m"),
                    contact_stiffness=Quantity(magnitude=1e5, unit="N/m"))  # fmt: skip
    with pytest.raises(RefusalError, match="contact_stiffness"):
        drop_screen(mass=Quantity(magnitude=1, unit="kg"), height=Quantity(magnitude=1, unit="m"),
                    contact_stiffness=Quantity(magnitude=1e5, unit="N"))  # fmt: skip
