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

Sources: Pozar, *Microwave Engineering*, for the characteristic-impedance,
reflection and standing-wave relations.
"""

from __future__ import annotations

from math import log, log10, pi, sqrt

from ..units import Quantity

__all__ = [
    "coaxial_characteristic_impedance",
    "mismatch_loss",
    "quarter_wave_transformer_impedance",
    "reflection_coefficient",
    "reflection_coefficient_from_vswr",
    "return_loss",
    "voltage_standing_wave_ratio",
]


_VACUUM_PERMEABILITY = 4e-7 * pi
_VACUUM_PERMITTIVITY = 8.8541878128e-12


def coaxial_characteristic_impedance(
    *,
    inner_radius: Quantity,
    outer_radius: Quantity,
    relative_permittivity: float = 1.0,
) -> Quantity:
    """The characteristic impedance of a coaxial line from its geometry, Z_0 = (eta/2pi)*ln(b/a).

    Every other function here *consumes* a characteristic impedance; this is the one that produces
    it. For a coax of ``inner_radius`` a (the center conductor), ``outer_radius`` b (the shield),
    and a dielectric of ``relative_permittivity`` eps_r between them,
    Z_0 = sqrt(mu_0/eps_0)/(2*pi*sqrt(eps_r)) * ln(b/a) = (59.96/sqrt(eps_r))*ln(b/a) ohm. Only the
    *ratio* b/a matters, not the absolute size — which is why a thin coax and a rigid line can share
    the same 50 ohm impedance, and why the 50 and 75 ohm standards are really the geometry ratios
    2.3 and 3.5 in air. Filling the line with a dielectric drops Z_0 by sqrt(eps_r), so a PTFE coax
    needs a fatter center conductor than an air line of the same impedance. Feed the result to
    :func:`reflection_coefficient` or :func:`quarter_wave_transformer_impedance`. Returns the
    characteristic impedance in ohm.
    """
    _check(inner_radius, "[length]", "inner_radius")
    _check(outer_radius, "[length]", "outer_radius")
    a = inner_radius.to("m").magnitude
    b = outer_radius.to("m").magnitude
    if a <= 0:
        raise ValueError("inner_radius must be positive")
    if b <= a:
        raise ValueError("outer_radius must exceed inner_radius")
    if relative_permittivity < 1:
        raise ValueError("relative_permittivity must be at least 1")
    eta = sqrt(_VACUUM_PERMEABILITY / _VACUUM_PERMITTIVITY)
    return Quantity(magnitude=eta / (2 * pi * sqrt(relative_permittivity)) * log(b / a), unit="ohm")


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


def mismatch_loss(*, reflection_coefficient: float) -> float:
    """The mismatch loss, ML = -10*log10(1 - |Gamma|²).

    The fraction of incident power *not* delivered to the load because it is reflected, in
    decibels: ML = -10*log10(1 - |``reflection_coefficient``|²). Distinct from :func:`return_loss`
    (which rates the reflected power) — mismatch loss rates the *transmitted* power lost, the number
    a link budget docks for an imperfect match. A small Gamma barely costs anything (Gamma = 0.2
    loses only 0.18 dB), which is why modest reflections are often tolerated. Returns the mismatch
    loss in dB as a plain float (>= 0).
    """
    g = abs(reflection_coefficient)
    if g >= 1.0:
        raise ValueError("|reflection_coefficient| must be below 1 (a full reflection loses all)")
    return -10.0 * log10(1.0 - g * g)


def reflection_coefficient_from_vswr(*, voltage_standing_wave_ratio: float) -> float:
    """The reflection-coefficient magnitude from VSWR, |Gamma| = (VSWR - 1)/(VSWR + 1).

    The measurement inverse of :func:`voltage_standing_wave_ratio`: an instrument reads a standing-
    wave ratio, and |Gamma| = (``voltage_standing_wave_ratio`` - 1)/(VSWR + 1) recovers the
    reflection coefficient magnitude behind it (which then feeds :func:`return_loss` or
    :func:`mismatch_loss`). A VSWR of 1 is a perfect match (Gamma = 0); as VSWR → ∞, |Gamma| → 1.
    ``voltage_standing_wave_ratio`` must be at least 1. Returns the reflection coefficient magnitude
    (0 to 1) as a plain float.
    """
    if voltage_standing_wave_ratio < 1.0:
        raise ValueError("voltage_standing_wave_ratio must be at least 1")
    s = voltage_standing_wave_ratio
    return (s - 1.0) / (s + 1.0)


def quarter_wave_transformer_impedance(
    *, source_impedance: Quantity, load_impedance: Quantity
) -> Quantity:
    """The quarter-wave transformer impedance, Z_q = √(Z_0·Z_L).

    A quarter-wavelength line of the right impedance matches two unequal impedances with no
    reflection: the section must have Z_q = √(``source_impedance`` Z_0 · ``load_impedance`` Z_L),
    the geometric mean of the two it joins. It is the classic narrowband matching trick — a 50 Ω to
    a 100 Ω antenna wants a 70.7 Ω quarter-wave section — exact only at the frequency where the
    section is truly λ/4. Both impedances must be positive resistances. Returns the transformer
    characteristic impedance in ohms.
    """
    _check(source_impedance, "[resistance]", "source_impedance")
    _check(load_impedance, "[resistance]", "load_impedance")
    z0 = source_impedance.to("ohm").magnitude
    zl = load_impedance.to("ohm").magnitude
    if z0 <= 0:
        raise ValueError("source_impedance must be positive")
    if zl <= 0:
        raise ValueError("load_impedance must be positive")
    return Quantity(magnitude=sqrt(z0 * zl), unit="ohm")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
