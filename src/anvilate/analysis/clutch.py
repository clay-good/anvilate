"""T1 analytical disc clutch / brake friction torque (closed-form).

A disc clutch or a disc/plate brake transmits torque through friction between
annular faces pressed together by an axial force F. How the pressure distributes
across the annulus sets the torque:

- **Uniform wear** — after break-in the faces wear to a constant p·r, and the
  torque is T = μ·F·N·(r_o + r_i)/2, i.e. the force times the friction times the
  *mean* radius, over N friction surfaces.
- **Uniform pressure** — a new, rigid pair carries constant pressure, giving the
  slightly higher T = (2/3)·μ·F·N·(r_o³ − r_i³)/(r_o² − r_i²).

Uniform wear is the standard design basis because it is the lower (conservative)
torque and describes a run-in clutch. A brake is just a clutch with one side held,
so the same forms give its braking torque. ``N`` counts friction interfaces — a
single-plate clutch gripped on both faces has N = 2.

These are the Shigley forms for flat annular faces (a cone clutch adds a 1/sin α
wedge factor, not included). Force and radius inputs are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import radians, sin, sqrt

from ..units import Quantity
from ..units.rotation import angular_speed_rad_per_s

UNIFORM_WEAR = "uniform_wear"
UNIFORM_PRESSURE = "uniform_pressure"

__all__ = [
    "UNIFORM_WEAR",
    "UNIFORM_PRESSURE",
    "disc_clutch_torque",
    "disc_clutch_force_for_torque",
    "cone_clutch_torque",
    "clutch_engagement_energy",
    "brake_absorbed_energy",
    "centrifugal_clutch_torque",
    "centrifugal_clutch_engagement_speed",
]


def _require(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )


def _mean_radius_factor(outer_radius: Quantity, inner_radius: Quantity, theory: str) -> float:
    """The effective radius (in m) that multiplies μ·F·N for the chosen theory."""
    _require(outer_radius, "[length]", "outer_radius")
    _require(inner_radius, "[length]", "inner_radius")
    ro = outer_radius.to("m").magnitude
    ri = inner_radius.to("m").magnitude
    if ri < 0:
        raise ValueError(f"inner_radius must be non-negative; got {inner_radius}")
    if ro <= ri:
        raise ValueError(f"outer_radius ({outer_radius}) must exceed inner_radius ({inner_radius})")
    if theory == UNIFORM_WEAR:
        return (ro + ri) / 2.0
    if theory == UNIFORM_PRESSURE:
        return (2.0 / 3.0) * (ro**3 - ri**3) / (ro**2 - ri**2)
    raise ValueError(f"theory must be {UNIFORM_WEAR!r} or {UNIFORM_PRESSURE!r}; got {theory!r}")


def disc_clutch_torque(
    *,
    actuating_force: Quantity,
    outer_radius: Quantity,
    inner_radius: Quantity,
    friction_coefficient: float,
    surfaces: int = 1,
    theory: str = UNIFORM_WEAR,
) -> Quantity:
    """The torque a disc clutch or brake transmits, T = μ·F·N·r_eff.

    ``actuating_force`` F is the axial clamping force, ``outer_radius`` r_o and
    ``inner_radius`` r_i bound the friction annulus, ``friction_coefficient`` μ is
    the face friction, and ``surfaces`` N the number of friction interfaces (2 for a
    single plate gripped on both faces). ``theory`` selects the pressure
    distribution — :data:`UNIFORM_WEAR` (default, conservative) or
    :data:`UNIFORM_PRESSURE`. r_o must exceed r_i, μ be non-negative, and N a
    positive integer. Returns the torque in N·m.
    """
    _require(actuating_force, "[force]", "actuating_force")
    if friction_coefficient < 0:
        raise ValueError(f"friction_coefficient must be non-negative; got {friction_coefficient}")
    if surfaces < 1:
        raise ValueError(f"surfaces must be a positive integer; got {surfaces}")
    r_eff = _mean_radius_factor(outer_radius, inner_radius, theory)
    f = actuating_force.to("N").magnitude
    torque = friction_coefficient * f * surfaces * r_eff
    return Quantity(magnitude=torque, unit="N*m")


def disc_clutch_force_for_torque(
    *,
    torque: Quantity,
    outer_radius: Quantity,
    inner_radius: Quantity,
    friction_coefficient: float,
    surfaces: int = 1,
    theory: str = UNIFORM_WEAR,
) -> Quantity:
    """The axial clamping force to transmit a target ``torque``, F = T/(μ·N·r_eff).

    The inverse of :func:`disc_clutch_torque` — the actuator or spring force a
    clutch/brake needs to carry a required torque, for the same geometry, friction,
    surface count, and ``theory``. ``torque`` must be a torque and
    ``friction_coefficient`` positive. Returns the force in newtons.
    """
    _require(torque, "[force] * [length]", "torque")
    if friction_coefficient <= 0:
        raise ValueError(f"friction_coefficient must be positive; got {friction_coefficient}")
    if surfaces < 1:
        raise ValueError(f"surfaces must be a positive integer; got {surfaces}")
    r_eff = _mean_radius_factor(outer_radius, inner_radius, theory)
    t = torque.to("N*m").magnitude
    force = t / (friction_coefficient * surfaces * r_eff)
    return Quantity(magnitude=force, unit="N")


def cone_clutch_torque(
    *,
    actuating_force: Quantity,
    outer_radius: Quantity,
    inner_radius: Quantity,
    friction_coefficient: float,
    cone_half_angle: float,
    theory: str = UNIFORM_WEAR,
) -> Quantity:
    """The torque a cone clutch transmits, T = μ·F·r_eff/sin(α).

    A cone clutch wedges a conical member into a matching seat, so the axial
    ``actuating_force`` F presses the faces together with a normal force amplified
    by 1/sin(α) for the cone half-angle α — the same disc-clutch torque
    (:func:`disc_clutch_torque`) multiplied by that wedge factor. A shallow cone
    (small α) multiplies grip steeply but risks jamming. ``outer_radius`` r_o and
    ``inner_radius`` r_i bound the conical face (measured to the axis),
    ``friction_coefficient`` μ the face friction, ``cone_half_angle`` α the half
    angle **in degrees** (units layer carries no angles), and ``theory`` the
    pressure distribution as in :func:`disc_clutch_torque`. r_o must exceed r_i, μ
    be non-negative, and α in (0, 90). Returns the torque in N·m.
    """
    _require(actuating_force, "[force]", "actuating_force")
    if friction_coefficient < 0:
        raise ValueError(f"friction_coefficient must be non-negative; got {friction_coefficient}")
    if not 0 < cone_half_angle < 90:
        raise ValueError(f"cone_half_angle (degrees) must lie in (0, 90); got {cone_half_angle}")
    r_eff = _mean_radius_factor(outer_radius, inner_radius, theory)
    f = actuating_force.to("N").magnitude
    torque = friction_coefficient * f * r_eff / sin(radians(cone_half_angle))
    return Quantity(magnitude=torque, unit="N*m")


def clutch_engagement_energy(
    *,
    driving_inertia: Quantity,
    driven_inertia: Quantity,
    speed_difference: Quantity,
) -> Quantity:
    """The heat a clutch dissipates in one engagement, E = ½·(I₁·I₂/(I₁+I₂))·Δω².

    When a clutch closes between a ``driving_inertia`` I₁ and a ``driven_inertia`` I₂ turning at a
    ``speed_difference`` Δω, the two are dragged to a common speed and the lost kinetic energy is
    burned as friction heat: E = ½·(I₁·I₂/(I₁+I₂))·Δω². The striking result is that this heat
    depends only on the inertias and the speed gap — *not* on the clutch torque, which only sets how
    quickly the engagement happens. So a clutch cannot be made to run cooler by gripping harder; the
    friction faces must be sized to soak up this energy every cycle. Returns the energy in joules.
    """
    _require(driving_inertia, "[mass]*[length]**2", "driving_inertia")
    _require(driven_inertia, "[mass]*[length]**2", "driven_inertia")
    _require(speed_difference, "1/[time]", "speed_difference")
    i1 = driving_inertia.to("kg*m**2").magnitude
    i2 = driven_inertia.to("kg*m**2").magnitude
    d_omega = angular_speed_rad_per_s(speed_difference, name="speed_difference")
    if i1 <= 0 or i2 <= 0:
        raise ValueError("driving_inertia and driven_inertia must be positive")
    reduced = i1 * i2 / (i1 + i2)
    return Quantity(magnitude=0.5 * reduced * d_omega**2, unit="J")


def brake_absorbed_energy(*, inertia: Quantity, angular_velocity: Quantity) -> Quantity:
    """The energy a brake absorbs stopping a rotating load, E = ½·I·ω².

    A brake is a clutch with one side held fixed, so stopping a rotating ``inertia`` I turning at
    ``angular_velocity`` ω dumps its whole rotational kinetic energy into the friction material:
    E = ½·I·ω² (the I₂ → ∞ limit of :func:`clutch_engagement_energy`). It is the heat the brake must
    shed each stop — the number that sets the disc mass and the cooling, and that decides whether a
    long descent needs an engine or eddy-current brake to keep the friction brake from fading.
    Returns the absorbed energy in joules.
    """
    _require(inertia, "[mass]*[length]**2", "inertia")
    _require(angular_velocity, "1/[time]", "angular_velocity")
    i = inertia.to("kg*m**2").magnitude
    omega = angular_speed_rad_per_s(angular_velocity, name="angular_velocity")
    if i <= 0:
        raise ValueError("inertia must be positive")
    return Quantity(magnitude=0.5 * i * omega**2, unit="J")


def centrifugal_clutch_torque(
    *,
    shoe_count: int,
    shoe_mass: Quantity,
    center_of_gravity_radius: Quantity,
    angular_speed: Quantity,
    drum_radius: Quantity,
    friction_coefficient: float,
    spring_force: Quantity,
) -> Quantity:
    """The torque a centrifugal clutch transmits, T = N·μ·(m·ω²·r − F_s)·R.

    A centrifugal clutch engages itself with speed: each of the ``shoe_count`` N shoes of
    ``shoe_mass`` m, its centre of gravity at ``center_of_gravity_radius`` r, is flung out against
    the drum by the centrifugal force m·ω²·r at ``angular_speed`` ω, less the ``spring_force`` F_s
    that holds it back below engagement. The net normal force, times the ``friction_coefficient`` μ
    and the ``drum_radius`` R, gives the torque per shoe, so T = N·μ·(m·ω²·r − F_s)·R. Below the
    engagement speed the springs win and the torque is zero (reported as 0, not negative) — the
    self-engaging behaviour of a chainsaw, moped, or go-kart drive. Returns the torque in N·m.
    """
    _require(shoe_mass, "[mass]", "shoe_mass")
    _require(center_of_gravity_radius, "[length]", "center_of_gravity_radius")
    _require(angular_speed, "1/[time]", "angular_speed")
    _require(drum_radius, "[length]", "drum_radius")
    _require(spring_force, "[force]", "spring_force")
    if shoe_count < 1:
        raise ValueError("shoe_count must be a positive integer")
    m = shoe_mass.to("kg").magnitude
    r_cg = center_of_gravity_radius.to("m").magnitude
    omega = angular_speed_rad_per_s(angular_speed, name="angular_speed")
    r_drum = drum_radius.to("m").magnitude
    f_spring = spring_force.to("N").magnitude
    if m <= 0 or r_cg <= 0 or r_drum <= 0:
        raise ValueError("shoe_mass, center_of_gravity_radius, and drum_radius must be positive")
    if omega < 0:
        raise ValueError("angular_speed must be non-negative")
    if friction_coefficient <= 0:
        raise ValueError("friction_coefficient must be positive")
    if f_spring < 0:
        raise ValueError("spring_force must be non-negative")
    net_force = m * omega**2 * r_cg - f_spring
    if net_force <= 0:
        return Quantity(magnitude=0.0, unit="N*m")
    return Quantity(magnitude=shoe_count * friction_coefficient * net_force * r_drum, unit="N*m")


def centrifugal_clutch_engagement_speed(
    *,
    shoe_mass: Quantity,
    center_of_gravity_radius: Quantity,
    spring_force: Quantity,
) -> Quantity:
    """The speed at which a centrifugal clutch begins to engage, ω = √(F_s/(m·r)).

    The clutch grips only once the centrifugal force on a shoe overcomes its retaining spring, so
    the engagement speed is where m·ω²·r = F_s, i.e. ω = √(F_s/(m·r)) — from the ``spring_force``
    F_s, the ``shoe_mass`` m, and the ``center_of_gravity_radius`` r. Below it the transmitted
    torque is zero; the spring preload is chosen to set this idle-disengagement speed so the engine
    can idle without driving the load. A stiffer spring or a lighter shoe raises it. Returns the
    engagement speed in rad/s.
    """
    _require(shoe_mass, "[mass]", "shoe_mass")
    _require(center_of_gravity_radius, "[length]", "center_of_gravity_radius")
    _require(spring_force, "[force]", "spring_force")
    m = shoe_mass.to("kg").magnitude
    r_cg = center_of_gravity_radius.to("m").magnitude
    f_spring = spring_force.to("N").magnitude
    if m <= 0 or r_cg <= 0:
        raise ValueError("shoe_mass and center_of_gravity_radius must be positive")
    if f_spring <= 0:
        raise ValueError("spring_force must be positive")
    return Quantity(magnitude=sqrt(f_spring / (m * r_cg)), unit="rad/s")
