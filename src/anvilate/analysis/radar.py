"""T1 analytical radar checks — Doppler and range equation (closed-form).

A radar measures a target's speed from the frequency shift of its echo, and its detection range from
how much of the transmitted power comes back. Because the wave travels to the target and back, the
Doppler shift is twice what a one-way source would give — the factor that sets a speed gun's
reading — and the echo power falls as the fourth power of range, which is what makes long-range
radar so power-hungry. This is distinct from the one-way acoustic Doppler of
:mod:`anvilate.analysis.acoustics`.

The two-way Doppler shift of an echo is f_d = 2*v*f0/c, from the radial velocity v, the transmit
frequency f0, and the speed of light c; inverting it turns a measured shift into speed. A pulsed
radar's finite pulse repetition frequency PRF caps both the unambiguous velocity PRF*c/(4*f0) and
the unambiguous range c/(2*PRF). The radar range equation gives the echo power P_r =
P_t*G²*λ²*σ/((4π)³*R⁴), and inverting it at the minimum detectable power gives the detection range
R_max = [P_t*G²*λ²*σ/((4π)³*P_min)]^(1/4). Inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import pi

from ..units import Quantity

_SPEED_OF_LIGHT = 299792458.0  # m/s

__all__ = [
    "max_unambiguous_range",
    "max_unambiguous_velocity",
    "radar_doppler_shift",
    "radar_max_range",
    "radar_received_power",
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


def max_unambiguous_range(*, pulse_repetition_frequency: Quantity) -> Quantity:
    """The maximum unambiguous range, R_u = c/(2*PRF).

    The farthest range a pulsed radar can measure without range ambiguity: the echo must return
    before the next pulse goes out, so from the ``pulse_repetition_frequency`` PRF,
    R_u = c/(2*PRF). A higher PRF (which widens the velocity window) shrinks this range window — the
    fundamental range-velocity trade of pulse-Doppler radar. Returns R_u in m.
    """
    _check(pulse_repetition_frequency, "1/[time]", "pulse_repetition_frequency")
    prf = pulse_repetition_frequency.to("Hz").magnitude
    if prf <= 0:
        raise ValueError("pulse_repetition_frequency must be positive")
    return Quantity(magnitude=_SPEED_OF_LIGHT / (2.0 * prf), unit="m")


def radar_received_power(
    *,
    transmit_power: Quantity,
    antenna_gain: float,
    wavelength: Quantity,
    target_cross_section: Quantity,
    target_range: Quantity,
) -> Quantity:
    """The radar received (echo) power, P_r = P_t*G²*λ²*σ/((4π)³*R⁴).

    The power returned to the radar from a target, from the ``transmit_power`` P_t, the (linear)
    ``antenna_gain`` G, the ``wavelength`` λ, the ``target_cross_section`` σ, and the
    ``target_range`` R: P_r = P_t*G²*λ²*σ/((4π)³*R⁴). The inverse-fourth-power range dependence is
    why doubling a radar's range needs sixteen times the power. Returns the received power in W.
    """
    _check(transmit_power, "[power]", "transmit_power")
    _check(wavelength, "[length]", "wavelength")
    _check(target_cross_section, "[area]", "target_cross_section")
    _check(target_range, "[length]", "target_range")
    p_t = transmit_power.to("W").magnitude
    lam = wavelength.to("m").magnitude
    sigma = target_cross_section.to("m**2").magnitude
    r = target_range.to("m").magnitude
    if p_t <= 0:
        raise ValueError("transmit_power must be positive")
    if antenna_gain <= 0:
        raise ValueError("antenna_gain must be positive")
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    if sigma <= 0:
        raise ValueError("target_cross_section must be positive")
    if r <= 0:
        raise ValueError("target_range must be positive")
    p_r = p_t * antenna_gain**2 * lam**2 * sigma / ((4.0 * pi) ** 3 * r**4)
    return Quantity(magnitude=p_r, unit="W")


def radar_max_range(
    *,
    transmit_power: Quantity,
    antenna_gain: float,
    wavelength: Quantity,
    target_cross_section: Quantity,
    min_detectable_power: Quantity,
) -> Quantity:
    """The radar detection range, R_max = [P_t*G²*λ²*σ/((4π)³*P_min)]^(1/4).

    The greatest range at which a target returns at least the minimum detectable power, by inverting
    the radar range equation: from the ``transmit_power`` P_t, the (linear) ``antenna_gain`` G, the
    ``wavelength`` λ, the ``target_cross_section`` σ, and the ``min_detectable_power`` P_min,
    R_max = [P_t*G²*λ²*σ/((4π)³*P_min)]^(1/4). The fourth-root makes range hard to extend.
    Returns the maximum range in m.
    """
    _check(transmit_power, "[power]", "transmit_power")
    _check(wavelength, "[length]", "wavelength")
    _check(target_cross_section, "[area]", "target_cross_section")
    _check(min_detectable_power, "[power]", "min_detectable_power")
    p_t = transmit_power.to("W").magnitude
    lam = wavelength.to("m").magnitude
    sigma = target_cross_section.to("m**2").magnitude
    p_min = min_detectable_power.to("W").magnitude
    if p_t <= 0:
        raise ValueError("transmit_power must be positive")
    if antenna_gain <= 0:
        raise ValueError("antenna_gain must be positive")
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    if sigma <= 0:
        raise ValueError("target_cross_section must be positive")
    if p_min <= 0:
        raise ValueError("min_detectable_power must be positive")
    r4 = p_t * antenna_gain**2 * lam**2 * sigma / ((4.0 * pi) ** 3 * p_min)
    return Quantity(magnitude=r4**0.25, unit="m")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
