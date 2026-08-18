"""T1 analytical centrifugal-separation checks (closed-form).

A centrifuge separates particles from a fluid by spinning the mixture so that the centrifugal field,
many thousands of times gravity, drives dense particles outward far faster than they would settle
under their own weight. This is the physics of the lab microcentrifuge, the milk separator, and the
decanter, and it is distinct from the gravity settling of :mod:`anvilate.analysis.drag`: the driving
acceleration is not the constant g but the position-dependent omega^2 * r, which grows with radius.

The field itself, RCF = omega^2 * r / g in multiples of gravity, is the G-factor of
:func:`anvilate.analysis.centrifugal_casting.centrifugal_g_factor`; this module adds the separation
physics on top of it. A particle in that field settles by Stokes' law with omega^2 * r in place of
g, so the sedimentation velocity is d^2 * (rho_p - rho_f) * omega^2 * r / (18 * mu). Because the
field rises with radius, the time for a particle to travel from an inner fill radius to the outer
wall is not distance/velocity but the integral t = 18 * mu * ln(r_o / r_i) / (omega^2 * d^2 * delta
rho) — the governing sizing relation for a tubular or decanter centrifuge.

Unlike the revolution-count rates of a conveyor or an impeller rim speed, the centrifugal
acceleration omega^2 * r is genuinely angular, so the rotational speed is taken as an angular rate
(rpm or rad/s, converted internally to rad/s).
"""

from __future__ import annotations

from math import log

from ..units import Quantity
from ..units.rotation import angular_speed_rad_per_s

__all__ = [
    "centrifugal_sedimentation_velocity",
    "centrifuge_settling_time",
]

# Stokes' law is the creeping-flow limit, and past a particle Reynolds number of about 1 the
# flow separates and the law overpredicts the velocity badly. :func:`drag.stokes_settling_velocity`
# already refuses past this line for gravity settling; substituting omega^2*r for g does not
# change the drag law, so the same limit applies here and is computable from the arguments.
_STOKES_REYNOLDS_LIMIT = 1.0


def _reject_beyond_stokes(
    *, velocity: float, diameter: float, density_fluid: float, viscosity: float, where: str
) -> None:
    """Refuse a Stokes result whose own implied particle Reynolds number breaks Stokes.

    The docstrings' "creeping-flow regime" is not advice — it is computable from the arguments
    already passed, and past it the answer is unconservative in the direction that matters. A
    100 um sand grain in water at 3,000 rpm and 150 mm returns 13.57 m/s at an implied Re of
    1,357; an iterated Schiller-Naumann solve gives 2.01 m/s. The velocity is 6.7x too fast and
    the settling time, which goes as 1/v, is 6.7x too short — so a centrifuge sized on it is
    undersized in residence time by that factor.
    """
    reynolds = density_fluid * abs(velocity) * diameter / viscosity
    if reynolds > _STOKES_REYNOLDS_LIMIT:
        raise ValueError(
            f"the centrifugal Stokes form is the creeping-flow limit and {where} implies a "
            f"particle Reynolds number of {reynolds:.4g}, past the "
            f"~{_STOKES_REYNOLDS_LIMIT:.0f} where it holds: the flow separates and this "
            f"result is an overprediction (6.7x for 100 um sand in water at 3,000 rpm). "
            f"Iterate on drag.sphere_drag_coefficient instead."
        )


def centrifugal_sedimentation_velocity(
    *,
    particle_diameter: Quantity,
    density_particle: Quantity,
    density_fluid: Quantity,
    viscosity: Quantity,
    radius: Quantity,
    rotational_speed: Quantity,
) -> Quantity:
    """The centrifugal Stokes settling velocity, v = d^2 (rho_p - rho_f) omega^2 r / (18 mu).

    Stokes' law with the centrifugal acceleration omega^2 * r in place of gravity: the outward
    speed of a ``particle_diameter`` d particle of ``density_particle`` rho_p in a ``density_fluid``
    rho_f, ``viscosity`` mu fluid at ``radius`` r and ``rotational_speed`` omega. It assumes a
    small, dilute, denser-than-fluid particle in the creeping-flow (low-Reynolds) regime — and
    **enforces it**: the particle Reynolds number implied by the result is checked against ~1
    and a result past it is refused rather than returned, because there it is an overprediction
    (6.7x for 100 um sand in water at 3,000 rpm and 150 mm). Returns the velocity in m/s
    (positive, radially outward).
    """
    _check(particle_diameter, "[length]", "particle_diameter")
    _check(density_particle, "[mass]/[length]**3", "density_particle")
    _check(density_fluid, "[mass]/[length]**3", "density_fluid")
    _check(viscosity, "[pressure]*[time]", "viscosity")
    _check(radius, "[length]", "radius")
    if not rotational_speed.has_dimension("1/[time]"):
        raise ValueError(
            f"rotational_speed must be a 1/[time] quantity; got "
            f"{rotational_speed.dimensionality} ({rotational_speed})"
        )
    d = particle_diameter.to("m").magnitude
    rho_p = density_particle.to("kg/m**3").magnitude
    rho_f = density_fluid.to("kg/m**3").magnitude
    mu = viscosity.to("Pa*s").magnitude
    r = radius.to("m").magnitude
    omega = angular_speed_rad_per_s(rotational_speed, name="rotational_speed")
    if d <= 0:
        raise ValueError("particle_diameter must be positive")
    if mu <= 0:
        raise ValueError("viscosity must be positive")
    if r <= 0:
        raise ValueError("radius must be positive")
    if omega <= 0:
        raise ValueError("rotational_speed must be positive")
    if rho_p <= rho_f:
        raise ValueError("density_particle must exceed density_fluid for outward sedimentation")
    v = d * d * (rho_p - rho_f) * omega * omega * r / (18.0 * mu)
    _reject_beyond_stokes(
        velocity=v,
        diameter=d,
        density_fluid=rho_f,
        viscosity=mu,
        where="the sedimentation velocity",
    )
    return Quantity(magnitude=v, unit="m/s")


def centrifuge_settling_time(
    *,
    particle_diameter: Quantity,
    density_particle: Quantity,
    density_fluid: Quantity,
    viscosity: Quantity,
    inner_radius: Quantity,
    outer_radius: Quantity,
    rotational_speed: Quantity,
) -> Quantity:
    """The centrifuge settling time, t = 18 mu ln(r_o / r_i) / (omega^2 d^2 delta_rho).

    The time a ``particle_diameter`` d particle takes to travel from an ``inner_radius`` r_i (the
    liquid surface, where the field is weakest) out to the ``outer_radius`` r_o wall in a fluid of
    ``density_fluid`` rho_f, ``viscosity`` mu spun at ``rotational_speed`` omega. Because the field
    omega^2 * r grows with radius, the travel time is the integral of dr/v, giving the ln term — the
    sizing relation for the residence time a tubular or decanter centrifuge must provide.

    Stokes' creeping-flow limit is enforced at the **outer** radius, where the field and so the
    velocity are highest: a particle that leaves the Stokes regime anywhere leaves it there
    first, and past it this time is short by the same factor the velocity is fast. Returns the
    time in s.
    """
    _check(particle_diameter, "[length]", "particle_diameter")
    _check(density_particle, "[mass]/[length]**3", "density_particle")
    _check(density_fluid, "[mass]/[length]**3", "density_fluid")
    _check(viscosity, "[pressure]*[time]", "viscosity")
    _check(inner_radius, "[length]", "inner_radius")
    _check(outer_radius, "[length]", "outer_radius")
    if not rotational_speed.has_dimension("1/[time]"):
        raise ValueError(
            f"rotational_speed must be a 1/[time] quantity; got "
            f"{rotational_speed.dimensionality} ({rotational_speed})"
        )
    d = particle_diameter.to("m").magnitude
    rho_p = density_particle.to("kg/m**3").magnitude
    rho_f = density_fluid.to("kg/m**3").magnitude
    mu = viscosity.to("Pa*s").magnitude
    r_i = inner_radius.to("m").magnitude
    r_o = outer_radius.to("m").magnitude
    omega = angular_speed_rad_per_s(rotational_speed, name="rotational_speed")
    if d <= 0:
        raise ValueError("particle_diameter must be positive")
    if mu <= 0:
        raise ValueError("viscosity must be positive")
    if not 0.0 < r_i < r_o:
        raise ValueError("inner_radius must be positive and less than outer_radius")
    if omega <= 0:
        raise ValueError("rotational_speed must be positive")
    if rho_p <= rho_f:
        raise ValueError("density_particle must exceed density_fluid for outward sedimentation")
    _reject_beyond_stokes(
        velocity=d * d * (rho_p - rho_f) * omega * omega * r_o / (18.0 * mu),
        diameter=d,
        density_fluid=rho_f,
        viscosity=mu,
        where="the velocity at the outer radius",
    )
    t = 18.0 * mu * log(r_o / r_i) / (omega * omega * d * d * (rho_p - rho_f))
    return Quantity(magnitude=t, unit="s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
