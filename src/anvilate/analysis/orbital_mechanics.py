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
    "hohmann_first_burn_delta_v",
    "hohmann_second_burn_delta_v",
    "hohmann_transfer_time",
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


def _hohmann_inputs(
    gravitational_parameter: Quantity, initial_radius: Quantity, final_radius: Quantity
) -> tuple[float, float, float, float]:
    """Validate and return (mu, r1, r2, a) in SI for a Hohmann transfer."""
    _check(gravitational_parameter, "[length]**3/[time]**2", "gravitational_parameter")
    _check(initial_radius, "[length]", "initial_radius")
    _check(final_radius, "[length]", "final_radius")
    mu = gravitational_parameter.to("m**3/s**2").magnitude
    r1 = initial_radius.to("m").magnitude
    r2 = final_radius.to("m").magnitude
    if mu <= 0:
        raise ValueError("gravitational_parameter must be positive")
    if r1 <= 0:
        raise ValueError("initial_radius must be positive")
    if r2 <= 0:
        raise ValueError("final_radius must be positive")
    if r2 == r1:
        raise ValueError("final_radius must differ from initial_radius (a transfer changes orbit)")
    return mu, r1, r2, (r1 + r2) / 2.0


def hohmann_first_burn_delta_v(
    *, gravitational_parameter: Quantity, initial_radius: Quantity, final_radius: Quantity
) -> Quantity:
    """The first Hohmann burn, Δv₁ = √(μ(2/r₁ − 1/a)) − √(μ/r₁).

    The velocity change that lifts a spacecraft from its circular ``initial_radius`` r₁ onto the
    transfer ellipse whose semi-major axis is a = (r₁ + r₂)/2 (with the ``final_radius`` r₂): from
    the ``gravitational_parameter`` μ, Δv₁ = √(μ(2/r₁ − 1/a)) − √(μ/r₁). It is positive (a prograde
    speed-up) for raising an orbit and negative for lowering one; the propulsive cost is its
    magnitude, and the total is |Δv₁| + |Δv₂| (:func:`hohmann_second_burn_delta_v`). Returns Δv₁ in
    m/s.
    """
    mu, r1, _r2, a = _hohmann_inputs(gravitational_parameter, initial_radius, final_radius)
    dv1 = sqrt(mu * (2.0 / r1 - 1.0 / a)) - sqrt(mu / r1)
    return Quantity(magnitude=dv1, unit="m/s")


def hohmann_second_burn_delta_v(
    *, gravitational_parameter: Quantity, initial_radius: Quantity, final_radius: Quantity
) -> Quantity:
    """The second Hohmann burn, Δv₂ = √(μ/r₂) − √(μ(2/r₂ − 1/a)).

    The velocity change that circularizes the spacecraft at the ``final_radius`` r₂, where the
    transfer ellipse (semi-major axis a = (r₁ + r₂)/2, from the ``initial_radius`` r₁) meets the
    target orbit: from the ``gravitational_parameter`` μ, Δv₂ = √(μ/r₂) − √(μ(2/r₂ − 1/a)). Like the
    first burn it is positive for raising an orbit; the total transfer cost is
    |Δv₁| + |Δv₂| (:func:`hohmann_first_burn_delta_v`). Returns Δv₂ in m/s.
    """
    mu, _r1, r2, a = _hohmann_inputs(gravitational_parameter, initial_radius, final_radius)
    dv2 = sqrt(mu / r2) - sqrt(mu * (2.0 / r2 - 1.0 / a))
    return Quantity(magnitude=dv2, unit="m/s")


def hohmann_transfer_time(
    *, gravitational_parameter: Quantity, initial_radius: Quantity, final_radius: Quantity
) -> Quantity:
    """The Hohmann coast time, t = π·√(a³/μ).

    The time the spacecraft spends coasting on the transfer ellipse — half its full period — between
    the two burns: from the ``gravitational_parameter`` μ and the semi-major axis a = (r₁ + r₂)/2
    of the ``initial_radius`` r₁ and ``final_radius`` r₂, t = π·√(a³/μ). It is fixed once the orbits
    are chosen and can run to hours or months, setting the wait a mission plans around (a LEO-to-GEO
    transfer takes about five hours). Returns the transfer time in s.
    """
    mu, _r1, _r2, a = _hohmann_inputs(gravitational_parameter, initial_radius, final_radius)
    return Quantity(magnitude=pi * sqrt(a**3 / mu), unit="s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
