"""T1 analytical Newtonian-gravitation checks (closed-form).

Every mass attracts every other with a force set by Newton's law of universal gravitation. The same
constant G fixes the weight you feel at a planet's surface and the strength of the field a probe
coasts through. This module supplies the fundamental force, the surface gravity, and the standard
gravitational parameter μ = G·M that the orbit relations of
:mod:`anvilate.analysis.orbital_mechanics` take as their input — so a mass here becomes an orbit
there.

The attractive force between two masses is F = G·m₁·m₂/r², from the masses m₁ and m₂ and their
centre-to-centre ``separation`` r; it falls off as the inverse square of distance. At the surface of
a body of mass M and radius R the field strength is g = G·M/R² — 9.82 m/s² for Earth. The grouping
μ = G·M, the standard gravitational parameter, is what actually governs orbits (it is known far more
precisely than G or M separately), and feeding it to the orbital-mechanics functions closes the loop
from a body's mass to the motion around it. Inputs and outputs are dimension-checked
:class:`~anvilate.units.Quantity` values.

Sources: Vallado, *Fundamentals of Astrodynamics and Applications* — Newton's law of universal
gravitation, the surface gravity of a body from its mass and radius, and the standard
gravitational parameter mu = G·M that orbital mechanics actually uses.
"""

from __future__ import annotations

from ..units import Quantity

_GRAVITATIONAL_CONSTANT = 6.67430e-11  # m**3/(kg*s**2)

__all__ = [
    "gravitational_force",
    "gravitational_parameter",
    "surface_gravity",
]


def gravitational_force(*, mass1: Quantity, mass2: Quantity, separation: Quantity) -> Quantity:
    """Newton's law of gravitation, F = G·m₁·m₂/r².

    The attractive force between two masses, from ``mass1`` m₁, ``mass2`` m₂, and their
    centre-to-centre ``separation`` r: F = G·m₁·m₂/r². It weakens as the inverse square of the
    distance, so doubling the separation quarters the pull. Returns the force in N.
    """
    _check(mass1, "[mass]", "mass1")
    _check(mass2, "[mass]", "mass2")
    _check(separation, "[length]", "separation")
    m1 = mass1.to("kg").magnitude
    m2 = mass2.to("kg").magnitude
    r = separation.to("m").magnitude
    if m1 <= 0 or m2 <= 0:
        raise ValueError("masses must be positive")
    if r <= 0:
        raise ValueError("separation must be positive")
    return Quantity(magnitude=_GRAVITATIONAL_CONSTANT * m1 * m2 / (r * r), unit="N")


def surface_gravity(*, mass: Quantity, radius: Quantity) -> Quantity:
    """The surface gravity, g = G·M/R².

    The gravitational field strength at the surface of a body of ``mass`` M and ``radius`` R:
    g = G·M/R² — the acceleration a dropped object feels, about 9.82 m/s² for Earth. A denser or
    larger body pulls harder. Returns the surface gravity in m/s**2.
    """
    _check(mass, "[mass]", "mass")
    _check(radius, "[length]", "radius")
    m = mass.to("kg").magnitude
    r = radius.to("m").magnitude
    if m <= 0:
        raise ValueError("mass must be positive")
    if r <= 0:
        raise ValueError("radius must be positive")
    return Quantity(magnitude=_GRAVITATIONAL_CONSTANT * m / (r * r), unit="m/s**2")


def gravitational_parameter(*, mass: Quantity) -> Quantity:
    """The standard gravitational parameter, μ = G·M.

    The product of the gravitational constant and a body's ``mass`` M: μ = G·M, the quantity that
    actually governs orbits (and is measured far more precisely than G or M alone). Pass the result
    to the :mod:`~anvilate.analysis.orbital_mechanics` functions as their gravitational-parameter
    input. Returns μ in m**3/s**2.
    """
    _check(mass, "[mass]", "mass")
    m = mass.to("kg").magnitude
    if m <= 0:
        raise ValueError("mass must be positive")
    return Quantity(magnitude=_GRAVITATIONAL_CONSTANT * m, unit="m**3/s**2")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
