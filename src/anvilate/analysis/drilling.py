"""T1 analytical twist-drilling checks (closed-form).

Drilling sinks a rotating twist drill into solid stock, its two cutting lips peeling a chip whose
thickness is set by the feed per revolution. It is the most common hole-making cut, and it sits
alongside the turning parameters of :mod:`anvilate.analysis.machining`: the same specific cutting
energy of the metal, applied to the geometry of a drill rather than a lathe tool. What a drill press
is sized on is not surface speed but *torque* — the twist the spindle must supply grows with the
square of the drill diameter, so a big drill in a tough metal can stall a machine that turns a small
one with ease.

Three numbers size a drilling cut. The material removal rate MRR = (π/4)·d²·f·N is the throughput —
the bore area (π/4)·d² swept forward at the feed per revolution f and the spindle speed N. The
torque M = u·f·d²/8 follows from the metal's specific cutting energy u and that same feed and
diameter; the d² is why torque, not speed, governs large drills. Inverting it gives the design
limit: the largest feed per revolution f_max = 8·M_limit/(u·d²) a spindle of a given torque rating
can pull without stalling — the number that sets how hard a hole can be pushed.
"""

from __future__ import annotations

from math import pi

from ..units import Quantity
from ..units.rotation import revolutions_per_minute

__all__ = [
    "drilling_feed_for_torque_limit",
    "drilling_material_removal_rate",
    "drilling_torque",
]


def drilling_material_removal_rate(
    *, drill_diameter: Quantity, feed_per_revolution: Quantity, spindle_speed: Quantity
) -> Quantity:
    """The drilling material removal rate, MRR = (π/4)·d²·f·N.

    The volume of metal a drill cuts per unit time: the bore cross-section (π/4)·d² of the
    ``drill_diameter`` d, advanced at the ``feed_per_revolution`` f and the ``spindle_speed`` N, so
    MRR = (π/4)·d²·f·N. It is the throughput of the hole, and — through the metal's specific cutting
    energy — the drive behind the spindle power. Returns the removal rate in cm**3/min.
    """
    _check(drill_diameter, "[length]", "drill_diameter")
    _check(feed_per_revolution, "[length]", "feed_per_revolution")
    _check(spindle_speed, "1/[time]", "spindle_speed")
    d = drill_diameter.to("mm").magnitude
    f = feed_per_revolution.to("mm").magnitude
    n = revolutions_per_minute(spindle_speed, name="spindle_speed")
    if d <= 0:
        raise ValueError("drill_diameter must be positive")
    if f <= 0:
        raise ValueError("feed_per_revolution must be positive")
    if n < 0:
        raise ValueError("spindle_speed must be non-negative")
    mrr_mm3_min = pi / 4.0 * d * d * f * n
    return Quantity(magnitude=mrr_mm3_min / 1000.0, unit="cm**3/min")


def drilling_torque(
    *, specific_cutting_energy: Quantity, feed_per_revolution: Quantity, drill_diameter: Quantity
) -> Quantity:
    """The drilling torque, M = u·f·d²/8.

    The twist the spindle must supply to drive the drill: from the metal's
    ``specific_cutting_energy`` u (the work to remove a unit volume, equal to its specific cutting
    force), the ``feed_per_revolution`` f, and the ``drill_diameter`` d, M = u·f·d²/8. It falls
    straight out of the cutting power P = u·MRR divided by the spindle's angular speed, and the d²
    dependence is why torque — not surface speed — is what a large drill in a tough metal is limited
    by. Compare it to the spindle's rated torque, or invert it with
    :func:`drilling_feed_for_torque_limit`. Returns the torque in N*m.
    """
    _check(specific_cutting_energy, "[pressure]", "specific_cutting_energy")
    _check(feed_per_revolution, "[length]", "feed_per_revolution")
    _check(drill_diameter, "[length]", "drill_diameter")
    u = specific_cutting_energy.to("Pa").magnitude
    f = feed_per_revolution.to("m").magnitude
    d = drill_diameter.to("m").magnitude
    if u <= 0:
        raise ValueError("specific_cutting_energy must be positive")
    if f <= 0:
        raise ValueError("feed_per_revolution must be positive")
    if d <= 0:
        raise ValueError("drill_diameter must be positive")
    return Quantity(magnitude=u * f * d * d / 8.0, unit="N*m")


def drilling_feed_for_torque_limit(
    *, torque_limit: Quantity, specific_cutting_energy: Quantity, drill_diameter: Quantity
) -> Quantity:
    """The largest feed a torque limit allows, f_max = 8·M_limit/(u·d²).

    Inverting the drilling torque (:func:`drilling_torque`) for feed: the greatest
    ``feed_per_revolution`` a spindle rated to a ``torque_limit`` M_limit can pull in a metal of
    ``specific_cutting_energy`` u with a drill of ``drill_diameter`` d, f_max = 8·M_limit/(u·d²).
    Feed above it demands more torque than the machine has and stalls the drill; the d² in the
    denominator is why the same spindle must feed a big drill far more gently than a small one.
    Returns the maximum feed per revolution in mm.
    """
    _check(torque_limit, "[force]*[length]", "torque_limit")
    _check(specific_cutting_energy, "[pressure]", "specific_cutting_energy")
    _check(drill_diameter, "[length]", "drill_diameter")
    m = torque_limit.to("N*m").magnitude
    u = specific_cutting_energy.to("Pa").magnitude
    d = drill_diameter.to("m").magnitude
    if m <= 0:
        raise ValueError("torque_limit must be positive")
    if u <= 0:
        raise ValueError("specific_cutting_energy must be positive")
    if d <= 0:
        raise ValueError("drill_diameter must be positive")
    f_max_m = 8.0 * m / (u * d * d)
    return Quantity(magnitude=f_max_m * 1000.0, unit="mm")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
