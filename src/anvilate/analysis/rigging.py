"""T1 analytical multi-leg sling / lifting checks (closed-form statics).

Lifting a load on a multi-leg sling is where a small angle quietly overloads the
hardware. Hang a weight ``W`` from ``n`` symmetric legs, each at an angle ``θ`` from the
horizontal, and vertical equilibrium gives each leg a tension

    T = W / (n · sin θ),

so the flatter the sling the harder every leg pulls: at a 30° leg angle each leg carries
*twice* what it would in a straight vertical lift, and the tension runs away toward
infinity as θ → 0. The same geometry drives a horizontal force H = W / (n · tan θ) inward
at each pick point — the crushing/spreading load a lifting beam or the lifted object
itself must take, and the side load that derates an eyebolt loaded off-axis.

So the design screen is: at the actual sling angle, is each leg's tension within the
sling's rated capacity, and is the horizontal pull within what the pick points and
spreader can take? The lesson these formulas encode is that sling capacity is an angle
problem, not just a weight problem.

The leg angle is a plain-float degrees value (the units layer carries no angles); the
load is a dimension-checked :class:`~anvilate.units.Quantity` and every force comes back
in the same force dimension.
"""

from __future__ import annotations

from math import radians, sin, tan

from ..units import Quantity

__all__ = [
    "sling_tension_factor",
    "sling_leg_tension",
    "sling_horizontal_force",
]


def _check_angle(angle_from_horizontal: float) -> float:
    if not 0 < angle_from_horizontal <= 90:
        raise ValueError(
            f"angle_from_horizontal must be in (0, 90] degrees; got {angle_from_horizontal}"
        )
    return angle_from_horizontal


def _check_legs(number_of_legs: int) -> int:
    if number_of_legs < 1:
        raise ValueError(f"number_of_legs must be at least 1; got {number_of_legs}")
    return number_of_legs


def sling_tension_factor(*, angle_from_horizontal: float) -> float:
    """The tension multiplier 1/sin θ of a sling leg at angle θ from horizontal.

    The factor by which a sling leg's tension exceeds its share of a straight vertical
    lift: 1 at 90° (vertical), 1.155 at 60°, 1.414 at 45°, 2 at 30°, and unbounded as
    the sling flattens toward horizontal. ``angle_from_horizontal`` θ is in degrees,
    (0, 90]. Returns the dimensionless factor.
    """
    theta = _check_angle(angle_from_horizontal)
    return 1.0 / sin(radians(theta))


def sling_leg_tension(
    *, load: Quantity, number_of_legs: int, angle_from_horizontal: float
) -> Quantity:
    """The tension T = W/(n·sin θ) in each leg of a symmetric multi-leg sling.

    A ``load`` W shared by ``number_of_legs`` n symmetric legs, each at
    ``angle_from_horizontal`` θ (degrees), puts T = W/(n·sin θ) in every leg — the share
    W/n amplified by the sling-angle factor (:func:`sling_tension_factor`). Screen it
    against the sling's rated capacity. Returns the tension in the load's force units.
    """
    _require_force(load)
    n = _check_legs(number_of_legs)
    theta = _check_angle(angle_from_horizontal)
    tension = load.to("N").magnitude / (n * sin(radians(theta)))
    return Quantity(magnitude=tension, unit="N")


def sling_horizontal_force(
    *, load: Quantity, number_of_legs: int, angle_from_horizontal: float
) -> Quantity:
    """The inward horizontal force H = W/(n·tan θ) each sling leg imposes.

    The horizontal component of each leg's tension, H = W/(n·tan θ) for a ``load`` W,
    ``number_of_legs`` n, and ``angle_from_horizontal`` θ (degrees). It is the crushing
    load a lifting beam or the lifted object takes at each pick point, and the off-axis
    side load that derates an eyebolt; it vanishes for a vertical lift (θ = 90°) and
    grows without bound as the sling flattens. Returns the force in the load's force
    units.
    """
    _require_force(load)
    n = _check_legs(number_of_legs)
    theta = _check_angle(angle_from_horizontal)
    horizontal = load.to("N").magnitude / (n * tan(radians(theta)))
    return Quantity(magnitude=horizontal, unit="N")


def _require_force(load: Quantity) -> None:
    if not load.has_dimension("[force]"):
        raise ValueError(f"load must be a [force] quantity; got {load.dimensionality} ({load})")
    if load.to("N").magnitude <= 0:
        raise ValueError(f"load must be positive; got {load}")
