"""T1 analytical metal-cutting (machining) checks (closed-form).

Setting up a turning, milling, or drilling cut comes down to a few relations between the spindle
speed, the tool or workpiece diameter, the feed and depth of cut, and how fast the tool then wears.
They decide the numbers a machinist dials in and the ones a process engineer screens a job against.

The cutting speed — the surface speed where the edge meets the metal — is V = π·D·N, the
circumference π·D turning at the spindle speed N. The right V for a tool-and-material pair is from
a handbook; the machine is set by its inverse, N = V/(π·D), the spindle speed that speed needs on a
given diameter. How fast metal comes off is the material removal rate MRR = V·f·d, the cutting speed
times the feed per revolution f and the depth of cut d — the productivity of the cut, and (times the
material's specific cutting energy) the spindle power it demands.

Push the cutting speed up and the tool wears out faster, by Taylor's tool-life law V·Tⁿ = C: the
life T = (C/V)^(1/n) falls steeply with speed, where C (a speed, the cutting speed for a one-minute
life) and the exponent n (~0.1–0.2 for high-speed steel, ~0.2–0.4 for carbide) are the tool's, from
test data. It is the trade at the heart of choosing a cutting speed — faster cuts, sooner-dulled
tools.
"""

from __future__ import annotations

from math import pi

from ..units import Quantity

__all__ = [
    "cutting_speed",
    "material_removal_rate",
    "spindle_speed_for_cutting_speed",
    "taylor_tool_life",
]


def cutting_speed(*, diameter: Quantity, spindle_speed: Quantity) -> Quantity:
    """The surface cutting speed, V = π·D·N.

    The speed at which the cutting edge sweeps the metal, from the ``diameter`` D (the workpiece in
    turning, the tool in milling or drilling) and the ``spindle_speed`` N: V = π·D·N. It is the
    parameter a handbook specifies for a tool-and-material pair — too high burns the edge, too low
    wastes the tool — and :func:`spindle_speed_for_cutting_speed` turns a target value back into an
    rpm. Returns the cutting speed in m/min.
    """
    _check(diameter, "[length]", "diameter")
    _check(spindle_speed, "1/[time]", "spindle_speed")
    d = diameter.to("m").magnitude
    n = spindle_speed.to("revolution/minute").magnitude
    if d <= 0:
        raise ValueError("diameter must be positive")
    if n < 0:
        raise ValueError("spindle_speed must be non-negative")
    return Quantity(magnitude=pi * d * n, unit="m/min")


def spindle_speed_for_cutting_speed(*, cutting_speed: Quantity, diameter: Quantity) -> Quantity:
    """The spindle speed for a target cutting speed, N = V/(π·D) (the inverse).

    The rpm a machine must run to reach a target ``cutting_speed`` V on a given ``diameter`` D:
    N = V/(π·D), the inverse of :func:`cutting_speed`. This is the practical setup calculation — the
    handbook gives V for the material, and the spindle follows from it and the diameter, so a given
    V means a higher rpm on a small drill than on a big workpiece. Returns the spindle speed in rpm.
    """
    _check(cutting_speed, "[length]/[time]", "cutting_speed")
    _check(diameter, "[length]", "diameter")
    v = cutting_speed.to("m/min").magnitude
    d = diameter.to("m").magnitude
    if v < 0:
        raise ValueError("cutting_speed must be non-negative")
    if d <= 0:
        raise ValueError("diameter must be positive")
    return Quantity(magnitude=v / (pi * d), unit="rpm")


def material_removal_rate(
    *,
    cutting_speed: Quantity,
    feed: Quantity,
    depth_of_cut: Quantity,
) -> Quantity:
    """The material removal rate, MRR = V·f·d.

    The volume of metal a cut removes per unit time, from the ``cutting_speed`` V, the ``feed`` f
    (the tool advance per revolution), and the ``depth_of_cut`` d: MRR = V·f·d. It is the
    productivity of the cut, and multiplied by the material's specific cutting energy it gives the
    spindle power the cut demands — the check against the machine's rating. ``feed`` is entered as
    the per-revolution advance (a length, e.g. 0.2 mm). Returns the removal rate in cm³/min.
    """
    _check(cutting_speed, "[length]/[time]", "cutting_speed")
    _check(feed, "[length]", "feed")
    _check(depth_of_cut, "[length]", "depth_of_cut")
    v = cutting_speed.to("mm/min").magnitude
    f = feed.to("mm").magnitude
    d = depth_of_cut.to("mm").magnitude
    if v < 0:
        raise ValueError("cutting_speed must be non-negative")
    if f <= 0 or d <= 0:
        raise ValueError("feed and depth_of_cut must be positive")
    return Quantity(magnitude=v * f * d / 1000.0, unit="cm**3/min")


def taylor_tool_life(
    *,
    cutting_speed: Quantity,
    taylor_speed_constant: Quantity,
    taylor_exponent: float,
) -> Quantity:
    """The Taylor tool life, T = (C/V)^(1/n).

    How long a cutting edge lasts before it must be reground or replaced, from Taylor's law
    V·Tⁿ = C: T = (C/V)^(1/n), at a ``cutting_speed`` V, with the ``taylor_speed_constant`` C (a
    speed — the cutting speed that gives a one-minute life) and the ``taylor_exponent`` n
    (~0.1–0.2 high-speed steel, ~0.2–0.4 carbide), both from the tool's test data. Because 1/n is
    large, life falls steeply as speed rises — the reason a modest speed cut runs far longer.
    Returns the tool life in minutes.
    """
    _check(cutting_speed, "[length]/[time]", "cutting_speed")
    _check(taylor_speed_constant, "[length]/[time]", "taylor_speed_constant")
    v = cutting_speed.to("m/min").magnitude
    c = taylor_speed_constant.to("m/min").magnitude
    if v <= 0 or c <= 0:
        raise ValueError("cutting_speed and taylor_speed_constant must be positive")
    if not 0.0 < taylor_exponent < 1.0:
        raise ValueError(f"taylor_exponent must be in (0, 1); got {taylor_exponent}")
    return Quantity(magnitude=(c / v) ** (1.0 / taylor_exponent), unit="min")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
