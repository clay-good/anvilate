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

from math import radians, sin

from ..units import Quantity

UNIFORM_WEAR = "uniform_wear"
UNIFORM_PRESSURE = "uniform_pressure"

__all__ = [
    "UNIFORM_WEAR",
    "UNIFORM_PRESSURE",
    "disc_clutch_torque",
    "disc_clutch_force_for_torque",
    "cone_clutch_torque",
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
