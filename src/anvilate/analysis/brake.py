"""T1 analytical band brake (Euler-Eytelwein wrap on a drum, closed-form).

A band brake wraps a flexible band (usually lined steel) around a rotating drum
and tightens it; friction between band and drum builds the band tension
exponentially around the wrap exactly as in the capstan relation
(:mod:`~anvilate.analysis.belt`), and the braking torque is the tension
difference acting at the drum radius:

    T = (T₁ − T₂)·D/2 = T₁·(1 − e^(−μ·β))·D/2

with T₁ the tight-side (anchor-side, against rotation) tension, μ the lining
friction, β the wrap angle, and D the drum diameter. The lining is protected by
capping its contact pressure, which peaks at the tight end of the band:

    p_max = 2·T₁/(b·D)

for a band width b — compared against the lining maker's allowable (a user
input, like any allowable stress).

These are the Shigley Ch. 16 band-brake forms. Tensions, lengths, and torques
are dimension-checked :class:`~anvilate.units.Quantity` values; the **wrap angle
is a plain float in radians**, matching :mod:`~anvilate.analysis.belt` (the
units layer does not carry dimensionless angles).
"""

from __future__ import annotations

from math import exp

from ..units import Quantity
from .belt import belt_max_transmissible_force

__all__ = [
    "band_brake_torque",
    "band_brake_tight_tension_for_torque",
    "band_brake_max_lining_pressure",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _drum_radius_m(drum_diameter: Quantity) -> float:
    _require(drum_diameter, "[length]", "drum_diameter")
    d = drum_diameter.to("m").magnitude
    if d <= 0:
        raise ValueError(f"drum_diameter must be positive; got {drum_diameter}")
    return d / 2.0


def band_brake_torque(
    *,
    tight_tension: Quantity,
    drum_diameter: Quantity,
    friction_coefficient: float,
    wrap_angle: float,
) -> Quantity:
    """The braking torque of a band brake, T = T₁·(1 − e^(−μ·β))·D/2.

    ``tight_tension`` T₁ is the band tension at the anchored (tight) end,
    ``drum_diameter`` D the drum it wraps, ``friction_coefficient`` μ the
    band-on-drum lining friction, and ``wrap_angle`` β the arc of contact **in
    radians**. The tension difference the wrap can develop
    (:func:`~anvilate.analysis.belt.belt_max_transmissible_force`) acts at the
    drum radius — this is the most torque the brake holds before the drum slips
    under the band. Returns the torque in N·m.
    """
    force = belt_max_transmissible_force(
        tight_tension=tight_tension,
        friction_coefficient=friction_coefficient,
        wrap_angle=wrap_angle,
    )
    radius = _drum_radius_m(drum_diameter)
    return Quantity(magnitude=force.to("N").magnitude * radius, unit="N*m")


def band_brake_tight_tension_for_torque(
    *,
    torque: Quantity,
    drum_diameter: Quantity,
    friction_coefficient: float,
    wrap_angle: float,
) -> Quantity:
    """The tight-side tension a braking torque requires, T₁ = 2T/(D·(1 − e^(−μ·β))).

    The inverse of :func:`band_brake_torque` — the anchor-side band tension the
    band, its anchor pin, and the lever must be sized for so the brake holds a
    target ``torque`` on a drum of ``drum_diameter``. ``friction_coefficient``
    must be positive and ``wrap_angle`` (radians) positive. Returns the tension
    in newtons.
    """
    _require(torque, "[force] * [length]", "torque")
    if friction_coefficient <= 0:
        raise ValueError(f"friction_coefficient must be positive; got {friction_coefficient}")
    if wrap_angle <= 0:
        raise ValueError(f"wrap_angle (radians) must be positive; got {wrap_angle}")
    t = torque.to("N*m").magnitude
    if t <= 0:
        raise ValueError(f"torque must be positive; got {torque}")
    radius = _drum_radius_m(drum_diameter)
    grip = 1.0 - exp(-friction_coefficient * wrap_angle)
    return Quantity(magnitude=t / (radius * grip), unit="N")


def band_brake_max_lining_pressure(
    *,
    tight_tension: Quantity,
    band_width: Quantity,
    drum_diameter: Quantity,
) -> Quantity:
    """The peak band-to-drum contact pressure, p_max = 2·T₁/(b·D).

    Band pressure follows the local band tension (p = 2·T/(b·D) from equilibrium
    of a band element), so it peaks at the tight end where the tension is T₁.
    Compare against the lining manufacturer's allowable pressure (a user input —
    e.g. ~0.34 MPa for woven lining, ~1 MPa for sintered) to size the band width
    ``band_width`` b for a drum of ``drum_diameter`` D. Returns the pressure in
    MPa.
    """
    _require(tight_tension, "[force]", "tight_tension")
    _require(band_width, "[length]", "band_width")
    t1 = tight_tension.to("N").magnitude
    if t1 < 0:
        raise ValueError(f"tight_tension must be non-negative; got {tight_tension}")
    b = band_width.to("mm").magnitude
    if b <= 0:
        raise ValueError(f"band_width must be positive; got {band_width}")
    d = drum_diameter.to("mm").magnitude
    if d <= 0:
        raise ValueError(f"drum_diameter must be positive; got {drum_diameter}")
    return Quantity(magnitude=2.0 * t1 / (b * d), unit="MPa")
