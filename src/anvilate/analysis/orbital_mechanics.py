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

from math import degrees, pi, sqrt

from ..units import Quantity

__all__ = [
    "circular_orbit_velocity",
    "escape_velocity",
    "hohmann_first_burn_delta_v",
    "hohmann_phase_angle",
    "hohmann_second_burn_delta_v",
    "hohmann_transfer_time",
    "orbit_specific_energy",
    "orbital_period",
    "semi_major_axis_from_apsides",
    "synodic_period",
    "vis_viva_velocity",
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


def synodic_period(*, first_period: Quantity, second_period: Quantity) -> Quantity:
    """The synodic period of two orbits, 1/T_syn = |1/T₁ − 1/T₂|.

    How often two bodies orbiting the same primary line up again (conjunction to conjunction): from
    their orbital periods ``first_period`` T₁ and ``second_period`` T₂, 1/T_syn = |1/T₁ − 1/T₂|, so
    T_syn = T₁·T₂/|T₂ − T₁|. The faster body laps the slower one once per synodic period, which is
    why Earth-Mars launch windows recur only about every 780 days (both periods near a year make the
    beat long), and why the inner planets return to the same evening-sky position on their own
    cadence. The two periods must differ. Returns the synodic period in the same time family (days).
    """
    _check(first_period, "[time]", "first_period")
    _check(second_period, "[time]", "second_period")
    t1 = first_period.to("s").magnitude
    t2 = second_period.to("s").magnitude
    if t1 <= 0 or t2 <= 0:
        raise ValueError("orbital periods must be positive")
    if t1 == t2:
        raise ValueError("periods must differ (identical periods never lap: infinite synodic)")
    return Quantity(magnitude=t1 * t2 / abs(t2 - t1), unit="s").to("day")


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


def vis_viva_velocity(
    *, gravitational_parameter: Quantity, radius: Quantity, semi_major_axis: Quantity
) -> Quantity:
    """The vis-viva orbital speed, v = √(μ(2/r − 1/a)).

    The master equation for orbital velocity: the speed of a body at radius r on any conic orbit of
    semi-major axis a, from the ``gravitational_parameter`` μ, the ``radius`` r from the focus, and
    the ``semi_major_axis`` a — v = √(μ(2/r − 1/a)). It reduces to the circular speed √(μ/r) when
    a = r (:func:`circular_orbit_velocity`), gives the fast perigee and slow apogee speeds of an
    ellipse at its two apsides, and generalizes to escape (a → ∞) and hyperbolic (a < 0) orbits.
    Returns the orbital velocity in m/s.
    """
    _check(gravitational_parameter, "[length]**3/[time]**2", "gravitational_parameter")
    _check(radius, "[length]", "radius")
    _check(semi_major_axis, "[length]", "semi_major_axis")
    mu = gravitational_parameter.to("m**3/s**2").magnitude
    r = radius.to("m").magnitude
    a = semi_major_axis.to("m").magnitude
    if mu <= 0:
        raise ValueError("gravitational_parameter must be positive")
    if r <= 0:
        raise ValueError("radius must be positive")
    if a <= 0:
        raise ValueError("semi_major_axis must be positive")
    term = 2.0 / r - 1.0 / a
    if term <= 0:
        raise ValueError("radius must be within the orbit (2/r must exceed 1/a)")
    return Quantity(magnitude=sqrt(mu * term), unit="m/s")


def orbit_specific_energy(
    *, gravitational_parameter: Quantity, semi_major_axis: Quantity
) -> Quantity:
    """The specific orbital energy, ε = −μ/(2a).

    The total mechanical energy per unit mass of an orbit, which depends only on the semi-major
    axis: from the ``gravitational_parameter`` μ and the ``semi_major_axis`` a, ε = −μ/(2a). It is
    negative for a bound (elliptical) orbit, exactly zero for a parabolic escape trajectory, and
    positive for a hyperbolic flyby, so its sign tells whether a trajectory is captured or escapes.
    Every burn that changes energy changes a, and vice versa. Returns the specific energy in J/kg.
    """
    _check(gravitational_parameter, "[length]**3/[time]**2", "gravitational_parameter")
    _check(semi_major_axis, "[length]", "semi_major_axis")
    mu = gravitational_parameter.to("m**3/s**2").magnitude
    a = semi_major_axis.to("m").magnitude
    if mu <= 0:
        raise ValueError("gravitational_parameter must be positive")
    if a <= 0:
        raise ValueError("semi_major_axis must be positive")
    return Quantity(magnitude=-mu / (2.0 * a), unit="J/kg")


def semi_major_axis_from_apsides(
    *, periapsis_radius: Quantity, apoapsis_radius: Quantity
) -> Quantity:
    """The semi-major axis of an ellipse, a = (r_p + r_a)/2.

    The semi-major axis of an elliptical orbit from its two apsides: the ``periapsis_radius`` r_p
    (closest approach) and the ``apoapsis_radius`` r_a (the farthest point), both measured from the
    focus, a = (r_p + r_a)/2 — the mean of the extremes. It is the quantity the period
    (:func:`orbital_period`), the energy (:func:`orbit_specific_energy`), and the vis-viva speed
    (:func:`vis_viva_velocity`) all key on, so sizing an ellipse starts here. Returns a in km.
    """
    _check(periapsis_radius, "[length]", "periapsis_radius")
    _check(apoapsis_radius, "[length]", "apoapsis_radius")
    r_p = periapsis_radius.to("m").magnitude
    r_a = apoapsis_radius.to("m").magnitude
    if r_p <= 0:
        raise ValueError("periapsis_radius must be positive")
    if r_a < r_p:
        raise ValueError("apoapsis_radius must not be less than periapsis_radius")
    return Quantity(magnitude=(r_p + r_a) / 2.0, unit="m").to("km")


def hohmann_phase_angle(
    *,
    initial_radius: Quantity,
    final_radius: Quantity,
) -> float:
    """The departure phase angle for a Hohmann transfer, φ = π·(1 − ((r₁+r₂)/(2·r₂))^1.5).

    The transfer burns say how much velocity a trip costs and :func:`hohmann_transfer_time` says
    how long it takes; :func:`synodic_period` says how often the chance comes round. This is the
    piece that says *when to go*: where the target must be, relative to the spacecraft, at the
    moment of the departure burn. The transfer takes half the transfer-ellipse period, and the
    target has to arrive at the far apse at exactly that moment, so it must lead the departure
    point by φ = π·(1 − ((r₁+r₂)/(2·r₂))^1.5), from the ``initial_radius`` r₁ and ``final_radius``
    r₂ (both measured from the central body's centre). For an outward transfer φ is positive — the
    target leads (Earth→Mars wants Mars about 44° ahead) — and for an inward one it is negative,
    meaning the target must trail. Missing the window means waiting one synodic period. Returns the
    phase angle in **degrees**.
    """
    _check(initial_radius, "[length]", "initial_radius")
    _check(final_radius, "[length]", "final_radius")
    r1 = initial_radius.to("m").magnitude
    r2 = final_radius.to("m").magnitude
    if r1 <= 0 or r2 <= 0:
        raise ValueError("initial_radius and final_radius must be positive")
    if r1 == r2:
        raise ValueError("final_radius must differ from initial_radius (a transfer changes orbit)")
    return degrees(pi * (1.0 - ((r1 + r2) / (2.0 * r2)) ** 1.5))


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
