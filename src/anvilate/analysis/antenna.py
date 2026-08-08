"""T1 analytical antenna / free-space RF-link checks (closed-form).

A radio signal spreads out as it travels, so the power a receiver captures falls with the square of
distance. The Friis transmission equation sets how much of a transmitter's power reaches a receiver
over a clear line of sight, given the two antenna gains and the wavelength. This is the link budget
behind every wireless range estimate — Wi-Fi, telemetry, satellite downlinks — and it is a distinct
propagation calculation from the acoustic inverse-square attenuation of
:mod:`anvilate.analysis.acoustics` (which carries no wavelength-dependent aperture term).

The free-space path loss is FSPL = (4*pi*d/lambda)^2, the factor by which an isotropic link loses
signal over a ``distance`` d at ``wavelength`` lambda; it grows with the square of both distance and
frequency. The Friis equation then gives the received power P_r = P_t * G_t * G_r *
(lambda/(4*pi*d))^2 from the transmit power and the linear (not dB) transmit and receive gains.
Inverting it for a receiver's minimum usable power gives the maximum line-of-sight range,
d = (lambda/(4*pi)) * sqrt(P_t * G_t * G_r / P_r_min) — the reach a link can be expected to hold.

Gains here are linear power ratios (not dBi); convert a dBi figure with G = 10^(dBi/10) first.
"""

from __future__ import annotations

from math import pi, sqrt

from ..units import Quantity

__all__ = [
    "free_space_path_loss",
    "max_line_of_sight_range",
    "received_power",
]


def free_space_path_loss(*, distance: Quantity, wavelength: Quantity) -> float:
    """The free-space path loss, FSPL = (4*pi*d/lambda)^2.

    The factor by which an isotropic radio link attenuates over a ``distance`` d at a ``wavelength``
    lambda, FSPL = (4*pi*d/lambda)^2. It rises with the square of distance and of frequency (shorter
    wavelength), so doubling the range or the frequency quadruples the loss. Returns the loss as a
    plain float power ratio (P_transmit/P_receive for isotropic antennas); take 10*log10 for dB.
    """
    _check(distance, "[length]", "distance")
    _check(wavelength, "[length]", "wavelength")
    d = distance.to("m").magnitude
    lam = wavelength.to("m").magnitude
    if d <= 0:
        raise ValueError("distance must be positive")
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    return (4.0 * pi * d / lam) ** 2


def received_power(
    *,
    transmit_power: Quantity,
    transmit_gain: float,
    receive_gain: float,
    distance: Quantity,
    wavelength: Quantity,
) -> Quantity:
    """The Friis received power, P_r = P_t * G_t * G_r * (lambda/(4*pi*d))^2.

    The power a receiver captures over a clear line of sight: the ``transmit_power`` P_t times the
    linear ``transmit_gain`` G_t and ``receive_gain`` G_r, cut by the free-space spreading factor
    (lambda/(4*pi*d))^2 for ``distance`` d and ``wavelength`` lambda. It is the heart of a link
    budget, telling whether the signal clears the receiver's sensitivity. Returns the power in W.
    """
    _check(transmit_power, "[power]", "transmit_power")
    _check(distance, "[length]", "distance")
    _check(wavelength, "[length]", "wavelength")
    p_t = transmit_power.to("W").magnitude
    d = distance.to("m").magnitude
    lam = wavelength.to("m").magnitude
    if p_t < 0:
        raise ValueError("transmit_power must be non-negative")
    if transmit_gain <= 0:
        raise ValueError("transmit_gain must be positive")
    if receive_gain <= 0:
        raise ValueError("receive_gain must be positive")
    if d <= 0:
        raise ValueError("distance must be positive")
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    p_r = p_t * transmit_gain * receive_gain * (lam / (4.0 * pi * d)) ** 2
    return Quantity(magnitude=p_r, unit="W")


def max_line_of_sight_range(
    *,
    transmit_power: Quantity,
    transmit_gain: float,
    receive_gain: float,
    receiver_sensitivity: Quantity,
    wavelength: Quantity,
) -> Quantity:
    """The maximum range, d = (lambda/(4*pi)) * sqrt(P_t * G_t * G_r / P_r_min).

    The design inverse of :func:`received_power`: the greatest line-of-sight ``distance`` at which
    the received power still meets a receiver's ``receiver_sensitivity`` P_r_min, given the
    ``transmit_power`` P_t, linear ``transmit_gain`` G_t and ``receive_gain`` G_r, and
    ``wavelength`` lambda. It is the reach a free-space link holds before the signal drops. Returns
    the range in m.
    """
    _check(transmit_power, "[power]", "transmit_power")
    _check(receiver_sensitivity, "[power]", "receiver_sensitivity")
    _check(wavelength, "[length]", "wavelength")
    p_t = transmit_power.to("W").magnitude
    p_min = receiver_sensitivity.to("W").magnitude
    lam = wavelength.to("m").magnitude
    if p_t <= 0:
        raise ValueError("transmit_power must be positive")
    if transmit_gain <= 0:
        raise ValueError("transmit_gain must be positive")
    if receive_gain <= 0:
        raise ValueError("receive_gain must be positive")
    if p_min <= 0:
        raise ValueError("receiver_sensitivity must be positive")
    if lam <= 0:
        raise ValueError("wavelength must be positive")
    d = (lam / (4.0 * pi)) * sqrt(p_t * transmit_gain * receive_gain / p_min)
    return Quantity(magnitude=d, unit="m")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
