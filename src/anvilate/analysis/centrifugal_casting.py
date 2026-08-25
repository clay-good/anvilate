"""T1 analytical centrifugal-casting checks (closed-form).

Centrifugal casting pours molten metal into a spinning mold and lets the rotation, not gravity, feed
and pack it. The centrifugal field throws the melt against the mold wall, so a cast pipe or ring
forms a dense, fine-grained outer skin while the lighter slag, gas, and oxide float inward to the
bore where they are machined away. It is a different lever on the same solidification the
:mod:`anvilate.analysis.casting` modulus governs: here the quality knob is the *spin speed*, and it
is set by one number.

That number is the G-factor G = ω²·r/g, the centrifugal acceleration at the mold wall in multiples
of gravity — run too low and the metal will not pack or the slag will not separate, too high and the
mold can tear or the metal spatter, so production runs a target band (typically tens to low hundreds
of G). Inverting it gives the practical setting: the angular speed ω = √(G·g/r) the mold must turn
to reach a chosen G at a given radius. The rotation also pressurizes the melt against the wall, a
metallostatic wall pressure p = ½·ρ·ω²·(r_o² − r_i²) that drives feeding and suppresses porosity —
the mechanism behind the sound outer skin.

Sources: Kalpakjian & Schmid, *Manufacturing Engineering and Technology* (centrifugal casting) —
the G factor a spinning mould develops at radius and speed, the speed a target G factor needs,
and the pressure the rotating melt puts on the mould wall.
"""

from __future__ import annotations

from math import sqrt

from ..units import Quantity
from ..units.rotation import angular_speed_rad_per_s

# Standard gravitational acceleration.
STANDARD_GRAVITY_M_PER_S2 = 9.80665

__all__ = [
    "centrifugal_g_factor",
    "centrifugal_speed_for_g_factor",
    "centrifugal_wall_pressure",
]


def centrifugal_g_factor(*, rotational_speed: Quantity, radius: Quantity) -> float:
    """The G-factor, G = ω²·r/g.

    The centrifugal acceleration the melt feels at the mold wall, in multiples of gravity: from the
    ``rotational_speed`` ω and the ``radius`` r of the wall, G = ω²·r/g. It is the single quality
    knob of centrifugal casting — too low and the metal will not pack against the wall or let the
    slag float clear, too high and the mold can tear — so production holds a target band, commonly
    tens to low hundreds of G. Invert it with :func:`centrifugal_speed_for_g_factor` to get the spin
    speed. Returns the G-factor as a dimensionless multiple of gravity.
    """
    _check(rotational_speed, "1/[time]", "rotational_speed")
    _check(radius, "[length]", "radius")
    omega = angular_speed_rad_per_s(rotational_speed, name="rotational_speed")
    r = radius.to("m").magnitude
    if omega <= 0:
        raise ValueError("rotational_speed must be positive")
    if r <= 0:
        raise ValueError("radius must be positive")
    return omega * omega * r / STANDARD_GRAVITY_M_PER_S2


def centrifugal_speed_for_g_factor(*, g_factor: float, radius: Quantity) -> Quantity:
    """The spin speed for a target G-factor, ω = √(G·g/r).

    Inverting the G-factor (:func:`centrifugal_g_factor`) for speed: the angular speed the mold must
    turn to reach a chosen ``g_factor`` G at the wall ``radius`` r, ω = √(G·g/r). It is the setting
    the process is dialled to — a larger-diameter mold needs a lower speed for the same G, which is
    why big pipe molds turn slowly and small rings turn fast. Returns the rotational speed in rpm.
    """
    _check(radius, "[length]", "radius")
    r = radius.to("m").magnitude
    if g_factor <= 0:
        raise ValueError("g_factor must be positive")
    if r <= 0:
        raise ValueError("radius must be positive")
    omega = sqrt(g_factor * STANDARD_GRAVITY_M_PER_S2 / r)
    return Quantity(magnitude=omega, unit="rad/s").to("rpm")


def centrifugal_wall_pressure(
    *,
    rotational_speed: Quantity,
    density: Quantity,
    inner_radius: Quantity,
    outer_radius: Quantity,
) -> Quantity:
    """The metallostatic wall pressure, p = ½·ρ·ω²·(r_o² − r_i²).

    The pressure the spinning melt exerts on the mold wall, the centrifugal analogue of a head of
    liquid: integrating ρ·ω²·r from the free surface at the ``inner_radius`` r_i (the bore) out to
    the wall at the ``outer_radius`` r_o gives p = ½·ρ·ω²·(r_o² − r_i²), from the ``density`` ρ and
    the ``rotational_speed`` ω. This pressure feeds the solidifying skin and squeezes out porosity —
    the reason the outer surface of a centrifugal casting comes out dense and sound. Returns it in
    MPa.
    """
    _check(rotational_speed, "1/[time]", "rotational_speed")
    _check(density, "[mass]/[length]**3", "density")
    _check(inner_radius, "[length]", "inner_radius")
    _check(outer_radius, "[length]", "outer_radius")
    omega = angular_speed_rad_per_s(rotational_speed, name="rotational_speed")
    rho = density.to("kg/m**3").magnitude
    r_i = inner_radius.to("m").magnitude
    r_o = outer_radius.to("m").magnitude
    if omega <= 0:
        raise ValueError("rotational_speed must be positive")
    if rho <= 0:
        raise ValueError("density must be positive")
    if r_i < 0:
        raise ValueError("inner_radius must be non-negative")
    if r_o <= r_i:
        raise ValueError("outer_radius must be greater than inner_radius")
    p_pa = 0.5 * rho * omega * omega * (r_o * r_o - r_i * r_i)
    return Quantity(magnitude=p_pa / 1.0e6, unit="MPa")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
