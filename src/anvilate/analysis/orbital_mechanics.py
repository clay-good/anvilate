"""T1 analytical orbital-mechanics checks (two-body, closed-form).

Once a rocket (:mod:`anvilate.analysis.rocket_propulsion`) has spent its Δv reaching orbital speed,
the vehicle coasts under gravity alone, and a few closed-form relations from the two-body problem
describe where it goes. They all hinge on one quantity, the gravitational parameter μ = G·M of the
body being orbited — known to high precision for the Earth, Moon, Sun, and planets — and the orbital
radius r from the body's center.

For a circular orbit, balancing gravity against the centripetal demand gives the orbital speed
v = √(μ/r): lower orbits are faster, which is why a spacecraft speeds up as it descends. The time to
go once around follows from Kepler's third law, T = 2π·√(r³/μ), growing with the three-halves power
of radius — the reason geostationary satellites sit far out. And the speed to break free of the body
entirely, leaving on a parabolic escape trajectory, is v_esc = √(2μ/r) = √2·v_circ — always exactly
√2 times the local circular speed, the extra velocity a mission to another body must find.
"""

from __future__ import annotations

from math import pi, sqrt

from ..units import Quantity

__all__ = [
    "circular_orbit_velocity",
    "escape_velocity",
    "orbital_period",
]


def circular_orbit_velocity(
    *, gravitational_parameter: Quantity, orbital_radius: Quantity
) -> Quantity:
    """The circular orbital speed, v = √(μ/r).

    The speed needed to hold a circular orbit, where gravity exactly supplies the centripetal
    acceleration: from the ``gravitational_parameter`` μ = G·M of the central body and the
    ``orbital_radius`` r measured from its center, v = √(μ/r). A lower orbit is faster — a satellite
    in low orbit outruns one higher up — which is the counter-intuitive heart of orbital rendezvous.
    Returns the orbital velocity in m/s.
    """
    _check(gravitational_parameter, "[length]**3/[time]**2", "gravitational_parameter")
    _check(orbital_radius, "[length]", "orbital_radius")
    mu = gravitational_parameter.to("m**3/s**2").magnitude
    r = orbital_radius.to("m").magnitude
    if mu <= 0:
        raise ValueError("gravitational_parameter must be positive")
    if r <= 0:
        raise ValueError("orbital_radius must be positive")
    return Quantity(magnitude=sqrt(mu / r), unit="m/s")


def orbital_period(*, gravitational_parameter: Quantity, orbital_radius: Quantity) -> Quantity:
    """The orbital period by Kepler's third law, T = 2π·√(r³/μ).

    The time a circular orbit takes to come around once: from the ``gravitational_parameter``
    μ = G·M and the ``orbital_radius`` r, T = 2π·√(r³/μ). It grows with the three-halves power of
    radius, so a small rise in altitude lengthens the period more than proportionally — the relation
    that places a
    geostationary satellite at a definite radius where the period matches one sidereal day. Returns
    the orbital period in s.
    """
    _check(gravitational_parameter, "[length]**3/[time]**2", "gravitational_parameter")
    _check(orbital_radius, "[length]", "orbital_radius")
    mu = gravitational_parameter.to("m**3/s**2").magnitude
    r = orbital_radius.to("m").magnitude
    if mu <= 0:
        raise ValueError("gravitational_parameter must be positive")
    if r <= 0:
        raise ValueError("orbital_radius must be positive")
    return Quantity(magnitude=2.0 * pi * sqrt(r**3 / mu), unit="s")


def escape_velocity(*, gravitational_parameter: Quantity, orbital_radius: Quantity) -> Quantity:
    """The escape velocity, v_esc = √(2μ/r) = √2·v_circ.

    The speed at which a body's kinetic energy just balances the gravitational well, leaving it on a
    parabolic trajectory that never returns: from the ``gravitational_parameter`` μ = G·M and the
    ``orbital_radius`` r, v_esc = √(2μ/r). It is always exactly √2 times the local circular speed
    (:func:`circular_orbit_velocity`), so a spacecraft in orbit needs only about 41% more speed to
    leave the body entirely — the velocity budget of any departure to another world. Returns the
    escape velocity in m/s.
    """
    _check(gravitational_parameter, "[length]**3/[time]**2", "gravitational_parameter")
    _check(orbital_radius, "[length]", "orbital_radius")
    mu = gravitational_parameter.to("m**3/s**2").magnitude
    r = orbital_radius.to("m").magnitude
    if mu <= 0:
        raise ValueError("gravitational_parameter must be positive")
    if r <= 0:
        raise ValueError("orbital_radius must be positive")
    return Quantity(magnitude=sqrt(2.0 * mu / r), unit="m/s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
