"""T1 analytical Coriolis / rotating-frame checks (closed-form).

In a rotating reference frame a moving body feels the Coriolis acceleration, at right angles to its
velocity and to the rotation axis. It is why weather systems and ocean currents turn, why a Foucault
pendulum precesses, why a long-range shell drifts sideways, and how a Coriolis mass flowmeter senses
flow. This is a distinct effect from the centrifugal field of :mod:`anvilate.analysis.centrifuge`
(which acts radially on anything in the frame): the Coriolis term acts only on motion, and across
the velocity.

The Coriolis acceleration is a_c = 2 * Omega * v for motion perpendicular to the rotation axis, from
the frame's angular rate Omega and the body's speed v. On a rotating planet the vertical part of the
rotation sets the Coriolis parameter f = 2 * Omega * sin(latitude), the local Coriolis frequency
that governs geophysical flow. Whether rotation matters to a flow is measured by the Rossby number
Ro = U / (f * L), the ratio of inertial to Coriolis forces over a length scale L: Ro much below 1
means rotation dominates (large-scale weather), Ro much above 1 means it is negligible (a draining
sink).

Sources: Cushman-Roisin & Beckers, *Introduction to Geophysical Fluid Dynamics* — the Coriolis
acceleration and its latitude parameter f = 2Ω·sin φ, the Foucault pendulum precession period,
and the Rossby and Ekman numbers that say when rotation and viscosity matter.
"""

from __future__ import annotations

from math import radians, sin

from ..units import Quantity
from ..units.rotation import angular_speed_rad_per_s

__all__ = [
    "coriolis_acceleration",
    "coriolis_parameter",
    "ekman_number",
    "foucault_precession_period",
    "rossby_number",
]

_SIDEREAL_DAY_HOURS = 23.9344696  # h (one rotation of Earth relative to the stars)


def coriolis_acceleration(*, angular_velocity: Quantity, velocity: Quantity) -> Quantity:
    """The Coriolis acceleration, a_c = 2 * Omega * v.

    The deflecting acceleration a body feels in a frame rotating at ``angular_velocity`` Omega while
    moving at ``velocity`` v perpendicular to the rotation axis, a_c = 2 * Omega * v. It acts across
    the motion, so it turns the path without changing speed. Returns the acceleration in
    m/s**2.
    """
    if not isinstance(angular_velocity, Quantity):
        raise ValueError(f"angular_velocity must be a 1/[time] quantity; got {angular_velocity!r}")
    if not angular_velocity.has_dimension("1/[time]"):
        raise ValueError(
            f"angular_velocity must be a 1/[time] quantity; got "
            f"{angular_velocity.dimensionality} ({angular_velocity})"
        )
    _check(velocity, "[length]/[time]", "velocity")
    omega = angular_speed_rad_per_s(angular_velocity, name="angular_velocity")
    v = velocity.to("m/s").magnitude
    if omega <= 0:
        raise ValueError("angular_velocity must be positive")
    if v < 0:
        raise ValueError("velocity must be non-negative")
    return Quantity(magnitude=2.0 * omega * v, unit="m/s**2")


def coriolis_parameter(*, angular_velocity: Quantity, latitude: float) -> Quantity:
    """The Coriolis parameter, f = 2 * Omega * sin(latitude).

    The local Coriolis frequency on a rotating planet: from the planet's ``angular_velocity`` Omega
    and the ``latitude`` (degrees), f = 2 * Omega * sin(latitude). It is zero at the equator and
    largest at the poles, and it sets the inertial-oscillation period and the strength of
    geostrophic balance in weather and ocean flow. Returns the Coriolis parameter in 1/s.
    """
    if not isinstance(angular_velocity, Quantity):
        raise ValueError(f"angular_velocity must be a 1/[time] quantity; got {angular_velocity!r}")
    if not angular_velocity.has_dimension("1/[time]"):
        raise ValueError(
            f"angular_velocity must be a 1/[time] quantity; got "
            f"{angular_velocity.dimensionality} ({angular_velocity})"
        )
    omega = angular_speed_rad_per_s(angular_velocity, name="angular_velocity")
    if omega <= 0:
        raise ValueError("angular_velocity must be positive")
    if not -90.0 <= latitude <= 90.0:
        raise ValueError("latitude must be in [-90, 90] degrees")
    return Quantity(magnitude=2.0 * omega * sin(radians(latitude)), unit="1/s")


def foucault_precession_period(*, latitude: float) -> Quantity:
    """The Foucault pendulum precession period, T = T_sidereal/sin|φ|.

    A long pendulum's swing plane slowly rotates as the Earth turns beneath it — Foucault's 1851
    proof that the planet spins. The plane completes one full turn in T = T_sidereal/sin|φ|, from
    the ``latitude`` φ (degrees), where T_sidereal ≈ 23.934 h is one rotation relative to the
    stars. At the pole the period is a full sidereal day; at 45° it is about 33.8 h; toward the
    equator it
    lengthens without bound (a pendulum there does not precess at all). ``latitude`` must be nonzero
    and within ±90°. Returns the precession period in hours.
    """
    if not -90.0 <= latitude <= 90.0:
        raise ValueError("latitude must be in [-90, 90] degrees")
    s = abs(sin(radians(latitude)))
    if s == 0.0:
        raise ValueError(
            "latitude must be nonzero: a Foucault pendulum at the equator does not precess "
            "(infinite period)"
        )
    return Quantity(magnitude=_SIDEREAL_DAY_HOURS / s, unit="hour")


def rossby_number(
    *, velocity: Quantity, coriolis_parameter: Quantity, length_scale: Quantity
) -> float:
    """The Rossby number, Ro = U / (f * L).

    The dimensionless ratio of inertial to Coriolis forces for a flow of speed ``velocity`` U over a
    ``length_scale`` L at a ``coriolis_parameter`` f, Ro = U / (f * L). Ro much below 1 means
    rotation dominates (synoptic weather, ocean gyres); Ro much above 1 means it is negligible
    (a bathtub vortex). Returns the Rossby number as a plain float.
    """
    _check(velocity, "[length]/[time]", "velocity")
    if not isinstance(coriolis_parameter, Quantity):
        raise ValueError(
            f"coriolis_parameter must be a 1/[time] quantity; got {coriolis_parameter!r}"
        )
    if not coriolis_parameter.has_dimension("1/[time]"):
        raise ValueError(
            f"coriolis_parameter must be a 1/[time] quantity; got "
            f"{coriolis_parameter.dimensionality} ({coriolis_parameter})"
        )
    _check(length_scale, "[length]", "length_scale")
    u = velocity.to("m/s").magnitude
    f = coriolis_parameter.to("1/s").magnitude
    length = length_scale.to("m").magnitude
    if f <= 0:
        raise ValueError("coriolis_parameter must be positive")
    if length <= 0:
        raise ValueError("length_scale must be positive")
    return u / (f * length)


def ekman_number(
    *, kinematic_viscosity: Quantity, coriolis_parameter: Quantity, length_scale: Quantity
) -> float:
    """The Ekman number, Ek = ν / (f·L²).

    The dimensionless ratio of viscous to Coriolis forces in a rotating flow: Ek = ν/(f·L²), from
    the ``kinematic_viscosity`` ν, the ``coriolis_parameter`` f, and the ``length_scale`` L. It is
    tiny for large-scale geophysical flow (rotation and pressure dominate, the interior is nearly
    inviscid and geostrophic) and only becomes order one inside the thin Ekman boundary layer at the
    bottom or surface, whose depth scales as √(ν/f). Together with the :func:`rossby_number` it
    closes the rotating-flow force balance — Ro/Ek = U·L/ν is exactly the Reynolds number. Returns
    the Ekman number as a plain float.
    """
    _check(kinematic_viscosity, "[length]**2/[time]", "kinematic_viscosity")
    if not isinstance(coriolis_parameter, Quantity):
        raise ValueError(
            f"coriolis_parameter must be a 1/[time] quantity; got {coriolis_parameter!r}"
        )
    if not coriolis_parameter.has_dimension("1/[time]"):
        raise ValueError(
            f"coriolis_parameter must be a 1/[time] quantity; got "
            f"{coriolis_parameter.dimensionality} ({coriolis_parameter})"
        )
    _check(length_scale, "[length]", "length_scale")
    nu = kinematic_viscosity.to("m**2/s").magnitude
    f = coriolis_parameter.to("1/s").magnitude
    length = length_scale.to("m").magnitude
    if nu <= 0:
        raise ValueError("kinematic_viscosity must be positive")
    if f <= 0:
        raise ValueError("coriolis_parameter must be positive")
    if length <= 0:
        raise ValueError("length_scale must be positive")
    return nu / (f * length**2)


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
