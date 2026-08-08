"""T1 analytical transmission-line impedance-matching checks (closed-form).

When a transmission line feeds a load whose impedance does not equal the line's, part of the wave
reflects back toward the source, setting up a standing wave and wasting power. How well a load is
matched is the central concern of RF and microwave interconnect — antennas, connectors, cables — and
it is captured by three related numbers. This complements the free-space link of
:mod:`anvilate.analysis.antenna`: the antenna radiates the power, and matching decides how much of
the transmitter's power reaches it rather than bouncing back.

The reflection coefficient is Gamma = (Z_L - Z_0)/(Z_L + Z_0), the fraction of the wave amplitude
reflected from a load ``Z_L`` on a line of characteristic impedance ``Z_0`` — zero for a perfect
match, +/-1 for an open or short. The voltage standing-wave ratio VSWR = (1 + |Gamma|)/(1 - |Gamma|)
measures the resulting ripple (1 is perfect, higher is worse). The return loss RL = -20*log10|Gamma|
expresses the same match in decibels of reflected power (higher dB is a better match). These treat
real (resistive) impedances; a complex load needs the full phasor form.
"""

from __future__ import annotations

from math import log10

from ..units import Quantity

__all__ = [
    "reflection_coefficient",
    "return_loss",
    "voltage_standing_wave_ratio",
]


def reflection_coefficient(
    *, load_impedance: Quantity, characteristic_impedance: Quantity
) -> float:
    """The reflection coefficient, Gamma = (Z_L - Z_0)/(Z_L + Z_0).

    The fraction of the wave amplitude reflected from a resistive load ``load_impedance`` Z_L on a
    line of ``characteristic_impedance`` Z_0: Gamma = (Z_L - Z_0)/(Z_L + Z_0). It is 0 for a
    perfect match, positive when the load exceeds the line (toward open), negative when below
    (toward short), and reaches +/-1 for an open or short. Returns Gamma as a float (in [-1, 1]).
    """
    _check(load_impedance, "[electric_potential]/[current]", "load_impedance")
    _check(characteristic_impedance, "[electric_potential]/[current]", "characteristic_impedance")
    z_l = load_impedance.to("ohm").magnitude
    z_0 = characteristic_impedance.to("ohm").magnitude
    if z_l < 0:
        raise ValueError("load_impedance must be non-negative")
    if z_0 <= 0:
        raise ValueError("characteristic_impedance must be positive")
    return (z_l - z_0) / (z_l + z_0)


def voltage_standing_wave_ratio(*, reflection_coefficient: float) -> float:
    """The voltage standing-wave ratio, VSWR = (1 + |Gamma|)/(1 - |Gamma|).

    The ratio of the maximum to minimum voltage of the standing wave a ``reflection_coefficient``
    Gamma sets up, VSWR = (1 + |Gamma|)/(1 - |Gamma|). It is 1 for a perfect match and rises without
    bound toward a total reflection; a VSWR under about 1.5 is usually considered a good match.
    Returns the VSWR as a plain float (>= 1).
    """
    g = abs(reflection_coefficient)
    if g >= 1.0:
        raise ValueError("|reflection_coefficient| must be below 1 (a full reflection is infinite)")
    return (1.0 + g) / (1.0 - g)


def return_loss(*, reflection_coefficient: float) -> float:
    """The return loss, RL = -20*log10(|Gamma|).

    The reflected power expressed in decibels below the incident power, from the
    ``reflection_coefficient`` Gamma: RL = -20*log10(|Gamma|). A larger return loss means a better
    match (less power reflected) — 20 dB reflects 1%, 10 dB reflects 10%. Returns the return loss in
    dB as a plain float.
    """
    g = abs(reflection_coefficient)
    if g <= 0.0:
        raise ValueError(
            "reflection_coefficient must be non-zero (a perfect match has infinite RL)"
        )
    if g > 1.0:
        raise ValueError("|reflection_coefficient| must not exceed 1")
    return -20.0 * log10(g)


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
