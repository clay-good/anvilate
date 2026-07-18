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

Those are the capstan forms for a stationary or slowly-moving band. A fast belt
also sheds grip to centrifugal tension T_c = m′·v² (belt mass per length m′ at
speed v), which lifts the belt off the pulley uniformly: only the *excess*
tension above T_c grips, so the ratio applies as (T₁ − T_c)/(T₂ − T_c) and the
transmissible force falls to (T₁ − T_c)·(1 − e^(−μ·β)). Since power is force
times the same speed that feeds T_c, transmitted power peaks at the classic
v* = √(T₁/(3·m′)) — run faster and the belt carries its own weight instead of
the load. Tensions are dimension-checked :class:`~anvilate.units.Quantity`
forces; the **wrap angle is a plain float in radians** (π for a half wrap, 2π
per full turn — the units layer does not carry dimensionless angles), matching
how μ is supplied.
"""

from __future__ import annotations

from math import asin, exp, pi, radians, sin, sqrt

from ..units import Quantity

__all__ = [
    "capstan_tension_ratio",
    "belt_slack_tension",
    "belt_max_transmissible_force",
    "belt_centrifugal_tension",
    "belt_max_transmissible_force_at_speed",
    "belt_speed_for_max_power",
    "vee_belt_effective_friction",
    "belt_length",
    "belt_wrap_angle",
    "crossed_belt_length",
    "crossed_belt_wrap_angle",
    "belt_transmitted_power",
    "belt_mean_tension",
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


def _linear_density_kg_per_m(linear_density: Quantity) -> float:
    if not linear_density.has_dimension("[mass] / [length]"):
        raise ValueError(
            f"linear_density must be a [mass]/[length] quantity; "
            f"got {linear_density.dimensionality} ({linear_density})"
        )
    m = linear_density.to("kg/m").magnitude
    if m <= 0:
        raise ValueError(f"linear_density must be positive; got {linear_density}")
    return m


def _speed_m_per_s(belt_speed: Quantity) -> float:
    if not belt_speed.has_dimension("[velocity]"):
        raise ValueError(
            f"belt_speed must be a [velocity] quantity; "
            f"got {belt_speed.dimensionality} ({belt_speed})"
        )
    v = belt_speed.to("m/s").magnitude
    if v < 0:
        raise ValueError(f"belt_speed must be non-negative; got {belt_speed}")
    return v


def belt_centrifugal_tension(*, linear_density: Quantity, belt_speed: Quantity) -> Quantity:
    """The centrifugal tension a moving belt carries, T_c = m′·v².

    A belt of mass per length ``linear_density`` m′ running at ``belt_speed`` v
    needs a tension m′·v² just to hold itself on the pulley arc — tension the
    drive pretensions into the belt but that presses nothing onto the pulley, so
    it grips nothing. Subtract it from the tight-side tension before applying the
    capstan relation (:func:`belt_max_transmissible_force_at_speed` does both).
    Returns the tension in newtons.
    """
    m = _linear_density_kg_per_m(linear_density)
    v = _speed_m_per_s(belt_speed)
    return Quantity(magnitude=m * v * v, unit="N")


def belt_max_transmissible_force_at_speed(
    *,
    tight_tension: Quantity,
    linear_density: Quantity,
    belt_speed: Quantity,
    friction_coefficient: float,
    wrap_angle: float,
) -> Quantity:
    """The maximum tangential force a *moving* belt transmits,
    (T₁ − m′·v²)·(1 − e^(−μ·β)).

    Centrifugal tension grips nothing, so only the tight tension in excess of
    T_c = m′·v² (:func:`belt_centrifugal_tension`) is available to the capstan
    relation — at v = 0 this reduces to :func:`belt_max_transmissible_force`, and
    it falls to zero at the speed where the belt's whole tension goes to carrying
    itself (past that the belt cannot transmit; this raises). ``tight_tension``
    T₁ is the belt's allowable (maximum) tension. Returns the force in newtons.
    """
    _require_force(tight_tension, "tight_tension")
    ratio = _ratio(friction_coefficient, wrap_angle)
    t1 = tight_tension.to("N").magnitude
    tc = belt_centrifugal_tension(linear_density=linear_density, belt_speed=belt_speed).magnitude
    if tc >= t1:
        raise ValueError(
            f"centrifugal tension ({tc:.1f} N) consumes the whole tight-side tension "
            f"({tight_tension}) at this speed; the belt cannot transmit"
        )
    return Quantity(magnitude=(t1 - tc) * (1.0 - 1.0 / ratio), unit="N")


def belt_speed_for_max_power(*, tight_tension: Quantity, linear_density: Quantity) -> Quantity:
    """The belt speed that maximises transmitted power, v* = √(T₁/(3·m′)).

    Power is the transmissible force times the belt speed, and the force sheds
    m′·v² of grip as the speed rises — the product peaks where the centrifugal
    tension has eaten exactly a third of the allowable tight tension ``T₁``.
    Below v* a faster belt carries more power; above it, more speed carries
    less. Returns the speed in m/s.
    """
    _require_force(tight_tension, "tight_tension")
    t1 = tight_tension.to("N").magnitude
    if t1 <= 0:
        raise ValueError(f"tight_tension must be positive; got {tight_tension}")
    m = _linear_density_kg_per_m(linear_density)
    return Quantity(magnitude=sqrt(t1 / (3.0 * m)), unit="m/s")


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


def _crossed_geometry(
    large_pulley_diameter: Quantity, small_pulley_diameter: Quantity, center_distance: Quantity
) -> tuple[float, float, float]:
    """Validate and return (D, d, C) in mm for a crossed two-pulley belt drive."""
    big, small, c = _pulley_geometry(large_pulley_diameter, small_pulley_diameter, center_distance)
    if c <= (big + small) / 2.0:
        raise ValueError(
            f"center_distance ({center_distance}) must exceed (D+d)/2 for a crossed belt "
            "(the pulleys would touch at the cross)"
        )
    return big, small, c


def crossed_belt_length(
    *,
    large_pulley_diameter: Quantity,
    small_pulley_diameter: Quantity,
    center_distance: Quantity,
) -> Quantity:
    """The length of a crossed belt over two pulleys,
    L = 2C + π(D+d)/2 + (D+d)²/(4C).

    A crossed belt figure-eights between the pulleys so they turn in *opposite*
    directions; because the belt crosses, its geometry uses the *sum* of the radii
    where the open belt (:func:`belt_length`) uses the difference, giving the
    (D+d)²/(4C) closing term. ``large_pulley_diameter`` D, ``small_pulley_diameter``
    d, and ``center_distance`` C must be positive lengths with C above (D+d)/2 so the
    pulleys clear at the cross. A crossed belt is always longer than the open belt on
    the same pulleys. Returns the length in mm.
    """
    big, small, c = _crossed_geometry(large_pulley_diameter, small_pulley_diameter, center_distance)
    length = 2.0 * c + pi * (big + small) / 2.0 + (big + small) ** 2 / (4.0 * c)
    return Quantity(magnitude=length, unit="mm")


def crossed_belt_wrap_angle(
    *,
    large_pulley_diameter: Quantity,
    small_pulley_diameter: Quantity,
    center_distance: Quantity,
) -> float:
    """The wrap angle of a crossed belt, β = π + 2·arcsin((D+d)/(2C)), in **radians**.

    Unlike the open belt — whose two pulleys wrap different arcs — a crossed belt
    wraps *both* pulleys over the same angle, and that angle exceeds 180° (the belt
    crossing bends it further around each pulley). The extra wrap grips harder and
    raises the transmissible force, at the cost of the belt rubbing itself where it
    crosses (so crossed belts wear faster and are not used with V-belts).
    ``large_pulley_diameter`` D, ``small_pulley_diameter`` d, and ``center_distance``
    C are as in :func:`crossed_belt_length`. Returns the common wrap angle in radians.
    """
    big, small, c = _crossed_geometry(large_pulley_diameter, small_pulley_diameter, center_distance)
    return pi + 2.0 * asin((big + small) / (2.0 * c))


def belt_transmitted_power(
    *, tight_tension: Quantity, slack_tension: Quantity, belt_speed: Quantity
) -> Quantity:
    """The power a belt transmits, P = (T₁ − T₂)·v.

    The useful output of a belt drive: the net tension difference between the tight
    and slack sides, times the belt speed. ``tight_tension`` T₁ and ``slack_tension``
    T₂ are the two side tensions (T₁ > T₂; T₂ from :func:`belt_slack_tension`) and
    ``belt_speed`` v the linear belt speed at the pulley (from a pitch-line velocity).
    At the slip limit T₁ − T₂ is :func:`belt_max_transmissible_force`, so this gives
    the drive's power ceiling. All must be positive and T₁ > T₂. Returns the power in
    watts.
    """
    _require_force(tight_tension, "tight_tension")
    _require_force(slack_tension, "slack_tension")
    if not belt_speed.has_dimension("[velocity]"):
        raise ValueError(
            f"belt_speed must be a [velocity] quantity; got "
            f"{belt_speed.dimensionality} ({belt_speed})"
        )
    t1 = tight_tension.to("N").magnitude
    t2 = slack_tension.to("N").magnitude
    v = belt_speed.to("m/s").magnitude
    if t1 <= t2:
        raise ValueError(
            f"tight_tension ({tight_tension}) must exceed slack_tension ({slack_tension})"
        )
    if v <= 0:
        raise ValueError(f"belt_speed must be positive; got {belt_speed}")
    return Quantity(magnitude=(t1 - t2) * v, unit="W")


def belt_mean_tension(*, tight_tension: Quantity, slack_tension: Quantity) -> Quantity:
    """The mean belt tension T_m = (T₁ + T₂)/2.

    The average of the tight and slack side tensions — the value that sets the belt's
    static (initial) tensioning and the net radial pull the belt puts on the shaft
    bearings (about 2·T_m into the pulley). ``tight_tension`` T₁ and ``slack_tension``
    T₂ are the two side tensions (both positive). Returns the mean tension in newtons.
    """
    _require_force(tight_tension, "tight_tension")
    _require_force(slack_tension, "slack_tension")
    t1 = tight_tension.to("N").magnitude
    t2 = slack_tension.to("N").magnitude
    if t1 <= 0 or t2 <= 0:
        raise ValueError("tight_tension and slack_tension must be positive")
    return Quantity(magnitude=(t1 + t2) / 2.0, unit="N")
