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

The other rigging staple is the block and tackle. Frictionless, ``n`` supporting rope
parts give a mechanical advantage of exactly n; with friction, hoisting forces each
sheave pass to raise the rope tension by 1/η (the per-sheave efficiency), so the parts
carry a geometric series of tensions and the lead line — after the last supporting part
and any lead sheaves — sees the largest of all. Summing the series gives the actual
mechanical advantage

    MA = (r^n − 1) / ((r − 1) · r^(n−1+j)),   r = 1/η,

with ``j`` extra sheave passes between the last supporting part and the winch; the lead
line tension is W/MA. At η = 1 this collapses to MA = n exactly. This is the closed form
behind the lead-line-factor tables in rigging handbooks, and it is why a worn
plain-bearing tackle hoists at far less than its part count.

The leg angle is a plain-float degrees value (the units layer carries no angles); the
sheave efficiency is the caller's per-sheave value (≈ 0.98 rolling-bearing, ≈ 0.94
plain-bearing sheaves); the load is a dimension-checked
:class:`~anvilate.units.Quantity` and every force comes back in the same force
dimension.

Sources: ASME B30.9 (slings) and ASME BTH-1 — the sling tension factor from the included angle,
the leg tension and horizontal force it produces, and the mechanical advantage of a tackle.
"""

from __future__ import annotations

from math import radians, sin, tan

from ..units import Quantity

__all__ = [
    "sling_tension_factor",
    "sling_leg_tension",
    "sling_horizontal_force",
    "tackle_mechanical_advantage",
    "tackle_lead_line_tension",
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


def tackle_mechanical_advantage(
    *,
    supporting_parts: int,
    sheave_efficiency: float,
    lead_sheaves: int = 0,
) -> float:
    """The actual hoisting mechanical advantage of a block and tackle with friction.

    ``supporting_parts`` n rope parts hold the moving block; each sheave pass while
    hoisting raises the rope tension by 1/η for a per-sheave ``sheave_efficiency`` η
    (the caller's value — about 0.98 for rolling-bearing sheaves, 0.94 for plain
    bushings), and ``lead_sheaves`` j counts the extra passes between the last
    supporting part and the winch (0 when the hand pulls the last part directly).
    Summing the geometric series of part tensions gives
    MA = (r^n − 1)/((r − 1)·r^(n−1+j)) with r = 1/η, which collapses to exactly n when
    η = 1 — friction always costs, so the actual advantage is always below the part
    count. Returns the dimensionless mechanical advantage.
    """
    n = _check_parts(supporting_parts)
    eta = _check_efficiency(sheave_efficiency)
    j = _check_lead_sheaves(lead_sheaves)
    if eta == 1.0:
        return float(n)
    r = 1.0 / eta
    return (r**n - 1.0) / ((r - 1.0) * r ** (n - 1 + j))


def tackle_lead_line_tension(
    *,
    load: Quantity,
    supporting_parts: int,
    sheave_efficiency: float,
    lead_sheaves: int = 0,
) -> Quantity:
    """The lead-line (winch) tension W/MA a tackle needs to hoist a load.

    The pull the winch or hand must supply to raise ``load`` W through a tackle of
    ``supporting_parts`` n with per-sheave ``sheave_efficiency`` η and ``lead_sheaves``
    j extra passes to the winch — the load over the actual mechanical advantage
    (:func:`tackle_mechanical_advantage`). This is the largest tension anywhere in the
    rope, so it is the number both the winch rating and the rope selection screen
    against; the frictionless estimate W/n understates it on every real tackle.
    Returns the tension in the load's force units.
    """
    _require_force(load)
    advantage = tackle_mechanical_advantage(
        supporting_parts=supporting_parts,
        sheave_efficiency=sheave_efficiency,
        lead_sheaves=lead_sheaves,
    )
    return Quantity(magnitude=load.to("N").magnitude / advantage, unit="N")


def _check_parts(supporting_parts: int) -> int:
    if supporting_parts < 1:
        raise ValueError(f"supporting_parts must be at least 1; got {supporting_parts}")
    return supporting_parts


def _check_efficiency(sheave_efficiency: float) -> float:
    if not 0 < sheave_efficiency <= 1:
        raise ValueError(f"sheave_efficiency must be in (0, 1]; got {sheave_efficiency}")
    return sheave_efficiency


def _check_lead_sheaves(lead_sheaves: int) -> int:
    if lead_sheaves < 0:
        raise ValueError(f"lead_sheaves must be non-negative; got {lead_sheaves}")
    return lead_sheaves


def _require_force(load: Quantity) -> None:
    if not load.has_dimension("[force]"):
        raise ValueError(f"load must be a [force] quantity; got {load.dimensionality} ({load})")
    if load.to("N").magnitude <= 0:
        raise ValueError(f"load must be positive; got {load}")
