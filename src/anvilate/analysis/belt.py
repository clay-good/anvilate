"""T1 analytical belt / capstan friction (Euler-Eytelwein, closed-form).

A flexible band wrapped around a drum — a flat belt on a pulley, a rope on a
bollard, a band brake — grips by friction, and the tension it can carry builds up
exponentially around the wrap. The Euler-Eytelwein (capstan) equation relates the
tight-side tension T₁ to the slack-side T₂ across a wrap angle β with friction
coefficient μ:

    T₁/T₂ = e^(μ·β)

so a few turns of rope around a post hold a load hundreds of times the hand force
on the free end. The most a belt can transmit before it slips is the difference
T₁ − T₂ = T₁·(1 − e^(−μ·β)); pushed past it the belt slips and the ratio caps at
e^(μ·β).

These are the classic capstan forms for a stationary or slowly-moving band; a
fast belt also sheds grip to centrifugal tension (not included here). Tensions are
dimension-checked :class:`~anvilate.units.Quantity` forces; the **wrap angle is a
plain float in radians** (π for a half wrap, 2π per full turn — the units layer
does not carry dimensionless angles), matching how μ is supplied.
"""

from __future__ import annotations

from math import asin, exp, pi, radians, sin

from ..units import Quantity

__all__ = [
    "capstan_tension_ratio",
    "belt_slack_tension",
    "belt_max_transmissible_force",
    "vee_belt_effective_friction",
    "belt_length",
    "belt_wrap_angle",
]


def _require_force(value: Quantity, name: str) -> None:
    if not value.has_dimension("[force]"):
        raise ValueError(f"{name} must be a [force] quantity; got {value.dimensionality} ({value})")


def _ratio(friction_coefficient: float, wrap_angle: float) -> float:
    if friction_coefficient < 0:
        raise ValueError(f"friction_coefficient must be non-negative; got {friction_coefficient}")
    if wrap_angle <= 0:
        raise ValueError(f"wrap_angle (radians) must be positive; got {wrap_angle}")
    return exp(friction_coefficient * wrap_angle)


def capstan_tension_ratio(*, friction_coefficient: float, wrap_angle: float) -> float:
    """The capstan tension ratio T₁/T₂ = e^(μ·β).

    ``friction_coefficient`` μ is the band-on-drum friction and ``wrap_angle`` β the
    total angle of contact **in radians** (π for a 180° wrap, 2π for each full
    turn). The ratio is the most the tight side can exceed the slack side before the
    band slips, and it grows exponentially with both μ and the wrap — the reason a
    capstan or bollard multiplies a small holding force so steeply. ``μ`` must be
    non-negative and ``β`` positive. Returns the dimensionless ratio.
    """
    return _ratio(friction_coefficient, wrap_angle)


def belt_slack_tension(
    *,
    tight_tension: Quantity,
    friction_coefficient: float,
    wrap_angle: float,
) -> Quantity:
    """The least slack-side tension T₂ = T₁/e^(μ·β) that holds without slipping.

    Given the tight-side tension ``tight_tension`` T₁, the smallest hold-side
    tension that keeps the band from slipping is T₁ divided by the
    :func:`capstan_tension_ratio` — the hand force on a bollard, or the spring
    preload a band brake needs. ``tight_tension`` must be a force; the friction and
    wrap arguments are as there. Returns the slack tension in newtons.
    """
    _require_force(tight_tension, "tight_tension")
    ratio = _ratio(friction_coefficient, wrap_angle)
    return Quantity(magnitude=tight_tension.to("N").magnitude / ratio, unit="N")


def belt_max_transmissible_force(
    *,
    tight_tension: Quantity,
    friction_coefficient: float,
    wrap_angle: float,
) -> Quantity:
    """The maximum tangential force a belt transmits before slipping,
    T₁ − T₂ = T₁·(1 − e^(−μ·β)).

    The net driving force (or braking force) the wrap develops at the slip limit,
    the difference between the tight and slack tensions when the ratio is at its
    e^(μ·β) maximum. Multiply by the pulley radius for the transmissible torque.
    ``tight_tension`` T₁ must be a force; the friction and wrap arguments are as in
    :func:`capstan_tension_ratio`. Returns the force in newtons.
    """
    _require_force(tight_tension, "tight_tension")
    ratio = _ratio(friction_coefficient, wrap_angle)
    t1 = tight_tension.to("N").magnitude
    return Quantity(magnitude=t1 * (1.0 - 1.0 / ratio), unit="N")


def vee_belt_effective_friction(*, friction_coefficient: float, groove_angle: float) -> float:
    """The effective friction coefficient μ' = μ/sin(β/2) of a V-belt in its groove.

    A V-belt wedges into a grooved pulley, so the sheave's flanks press on it far
    harder than a flat belt's single face — the geometry multiplies the effective
    friction to μ/sin(β/2) for the groove included angle β. Feed the result to
    :func:`capstan_tension_ratio` in place of the plain μ to get the V-belt's much
    steeper grip (a 38° groove roughly triples the effective friction). The physical
    ``friction_coefficient`` μ must be non-negative and ``groove_angle`` β a positive
    angle **in degrees** below 180°. Returns the dimensionless effective μ'.
    """
    if friction_coefficient < 0:
        raise ValueError(f"friction_coefficient must be non-negative; got {friction_coefficient}")
    if not 0 < groove_angle < 180:
        raise ValueError(f"groove_angle (degrees) must lie in (0, 180); got {groove_angle}")
    return friction_coefficient / sin(radians(groove_angle / 2.0))


def _pulley_geometry(
    large_pulley_diameter: Quantity, small_pulley_diameter: Quantity, center_distance: Quantity
) -> tuple[float, float, float]:
    """Validate and return (D, d, C) in mm for an open two-pulley belt drive."""
    for value, name in (
        (large_pulley_diameter, "large_pulley_diameter"),
        (small_pulley_diameter, "small_pulley_diameter"),
        (center_distance, "center_distance"),
    ):
        if not value.has_dimension("[length]"):
            raise ValueError(
                f"{name} must be a [length] quantity; got {value.dimensionality} ({value})"
            )
    big = large_pulley_diameter.to("mm").magnitude
    small = small_pulley_diameter.to("mm").magnitude
    c = center_distance.to("mm").magnitude
    if small <= 0 or c <= 0:
        raise ValueError("small_pulley_diameter and center_distance must be positive")
    if big < small:
        raise ValueError(
            f"large_pulley_diameter ({large_pulley_diameter}) must be at least "
            f"small_pulley_diameter ({small_pulley_diameter})"
        )
    if c <= (big - small) / 2.0:
        raise ValueError(
            f"center_distance ({center_distance}) is too small for the pulleys to clear"
        )
    return big, small, c


def belt_length(
    *,
    large_pulley_diameter: Quantity,
    small_pulley_diameter: Quantity,
    center_distance: Quantity,
) -> Quantity:
    """The length of an open belt over two pulleys,
    L = 2C + π(D+d)/2 + (D−d)²/(4C).

    The belt wraps each pulley over its arc and runs straight between them;
    summing gives L for ``large_pulley_diameter`` D, ``small_pulley_diameter`` d, and
    ``center_distance`` C. Use it to pick a stock belt or set the take-up. The
    diameters and centre distance must be positive lengths with C large enough for
    the pulleys to clear. Returns the length in mm.
    """
    big, small, c = _pulley_geometry(large_pulley_diameter, small_pulley_diameter, center_distance)
    length = 2.0 * c + pi * (big + small) / 2.0 + (big - small) ** 2 / (4.0 * c)
    return Quantity(magnitude=length, unit="mm")


def belt_wrap_angle(
    *,
    large_pulley_diameter: Quantity,
    small_pulley_diameter: Quantity,
    center_distance: Quantity,
) -> float:
    """The wrap angle on the small pulley of an open belt drive, in **radians**.

    β = π − 2·arcsin((D − d)/(2C)) — the arc the belt contacts the *small* pulley,
    which is under 180° and so grips less and slips first, making it the wrap to
    feed :func:`capstan_tension_ratio` when checking a belt drive's capacity.
    ``large_pulley_diameter`` D, ``small_pulley_diameter`` d, and ``center_distance``
    C are as in :func:`belt_length`. Returns the angle in radians (the units layer
    carries no angles).
    """
    big, small, c = _pulley_geometry(large_pulley_diameter, small_pulley_diameter, center_distance)
    return pi - 2.0 * asin((big - small) / (2.0 * c))
