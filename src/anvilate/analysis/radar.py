"""T1 analytical Doppler-radar checks (closed-form).

A radar measures a target's speed from the frequency shift of its echo. Because the wave travels to
the target and back, the Doppler shift is twice what a one-way source would give — the factor that
sets a police speed gun's reading and a weather radar's wind measurement. This is distinct from the
one-way acoustic Doppler of :mod:`anvilate.analysis.acoustics`: the round trip doubles the shift,
and a pulsed radar's finite pulse rate caps the speed it can measure without ambiguity.

The two-way Doppler shift of an echo is f_d = 2*v*f0/c, from the radial ``target`` velocity v, the
transmit frequency f0, and the speed of light c. Inverting it turns a measured shift into speed,
v = f_d*c/(2*f0) — the speed-gun readout. A pulse-Doppler radar samples the echo at its pulse
repetition frequency PRF, and the Nyquist limit on that sampling caps the unambiguous velocity at
v_max = PRF*c/(4*f0); a faster target aliases to a wrong (folded) speed.
"""

from __future__ import annotations

from ..units import Quantity

_SPEED_OF_LIGHT = 299792458.0  # m/s

__all__ = [
    "max_unambiguous_velocity",
    "radar_doppler_shift",
    "radial_velocity_from_doppler",
]


def radar_doppler_shift(*, transmit_frequency: Quantity, radial_velocity: Quantity) -> Quantity:
    """The two-way radar Doppler shift, f_d = 2*v*f0/c.

    The frequency shift of a radar echo from a target closing (or opening) at radial ``velocity`` v,
    for a ``transmit_frequency`` f0: f_d = 2*v*f0/c. The factor of two comes from the wave making a
    round trip, so a radar shift is double the one-way acoustic case. Returns the shift in Hz
    (positive for an approaching target as given).
    """
    _check(transmit_frequency, "1/[time]", "transmit_frequency")
    _check(radial_velocity, "[length]/[time]", "radial_velocity")
    f0 = transmit_frequency.to("Hz").magnitude
    v = radial_velocity.to("m/s").magnitude
    if f0 <= 0:
        raise ValueError("transmit_frequency must be positive")
    if v < 0:
        raise ValueError("radial_velocity must be non-negative")
    return Quantity(magnitude=2.0 * v * f0 / _SPEED_OF_LIGHT, unit="Hz")


def radial_velocity_from_doppler(
    *, transmit_frequency: Quantity, doppler_shift: Quantity
) -> Quantity:
    """The radial velocity from a Doppler shift, v = f_d*c/(2*f0).

    The speed-gun inverse of :func:`radar_doppler_shift`: the radial velocity a measured
    ``doppler_shift`` f_d implies for a ``transmit_frequency`` f0, v = f_d*c/(2*f0). It is how a
    police or weather radar turns a beat frequency into a speed. Returns the velocity in m/s.
    """
    _check(transmit_frequency, "1/[time]", "transmit_frequency")
    _check(doppler_shift, "1/[time]", "doppler_shift")
    f0 = transmit_frequency.to("Hz").magnitude
    fd = doppler_shift.to("Hz").magnitude
    if f0 <= 0:
        raise ValueError("transmit_frequency must be positive")
    if fd < 0:
        raise ValueError("doppler_shift must be non-negative")
    return Quantity(magnitude=fd * _SPEED_OF_LIGHT / (2.0 * f0), unit="m/s")


def max_unambiguous_velocity(
    *, transmit_frequency: Quantity, pulse_repetition_frequency: Quantity
) -> Quantity:
    """The maximum unambiguous velocity, v_max = PRF*c/(4*f0).

    The fastest radial velocity a pulse-Doppler radar can measure without aliasing: from the
    ``transmit_frequency`` f0 and the ``pulse_repetition_frequency`` PRF, v_max = PRF*c/(4*f0) (the
    Nyquist limit on sampling the echo phase at the PRF). A target faster than this folds to a wrong
    apparent speed, so raising the PRF extends the velocity window. Returns v_max in m/s.
    """
    _check(transmit_frequency, "1/[time]", "transmit_frequency")
    _check(pulse_repetition_frequency, "1/[time]", "pulse_repetition_frequency")
    f0 = transmit_frequency.to("Hz").magnitude
    prf = pulse_repetition_frequency.to("Hz").magnitude
    if f0 <= 0:
        raise ValueError("transmit_frequency must be positive")
    if prf <= 0:
        raise ValueError("pulse_repetition_frequency must be positive")
    return Quantity(magnitude=prf * _SPEED_OF_LIGHT / (4.0 * f0), unit="m/s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
