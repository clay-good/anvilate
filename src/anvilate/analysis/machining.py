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
    "cutting_power",
    "cutting_speed",
    "material_removal_rate",
    "spindle_speed_for_cutting_speed",
    "taylor_tool_life",
    "theoretical_surface_roughness",
    "peak_to_valley_roughness",
    "feed_for_surface_roughness",
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


def theoretical_surface_roughness(*, feed: Quantity, tool_nose_radius: Quantity) -> Quantity:
    """The theoretical turned surface roughness, Ra ≈ f²/(32·r).

    The ideal-geometry arithmetic-average roughness a single-point (turning) tool leaves as its nose
    traces feed marks: Ra ≈ ``feed``²/(32·``tool_nose_radius``), with ``feed`` f the per-revolution
    advance (a length) and ``tool_nose_radius`` r the tool-tip radius. A finer feed or a larger nose
    radius smooths the finish quadratically and linearly. It is a lower bound — the real finish is
    rougher from built-up edge, vibration, and tool wear. Returns Ra in µm.
    """
    _check(feed, "[length]", "feed")
    _check(tool_nose_radius, "[length]", "tool_nose_radius")
    f = feed.to("mm").magnitude
    r = tool_nose_radius.to("mm").magnitude
    if f <= 0:
        raise ValueError("feed must be positive")
    if r <= 0:
        raise ValueError("tool_nose_radius must be positive")
    ra_mm = f * f / (32.0 * r)
    return Quantity(magnitude=ra_mm * 1000.0, unit="micrometer")


def peak_to_valley_roughness(*, feed: Quantity, tool_nose_radius: Quantity) -> Quantity:
    """The theoretical peak-to-valley roughness, Rt ≈ f²/(8·r).

    The maximum height of the feed-mark cusps a turning tool leaves: Rt ≈
    ``feed``²/(8·``tool_nose_radius``), from the per-revolution ``feed`` f and the
    ``tool_nose_radius`` r. It is four times the arithmetic-average
    :func:`theoretical_surface_roughness` (Rt = 4·Ra for this ideal geometry), and is the measure a
    peak-to-valley spec or a sealing-surface requirement is written against. Returns Rt in µm.
    """
    _check(feed, "[length]", "feed")
    _check(tool_nose_radius, "[length]", "tool_nose_radius")
    f = feed.to("mm").magnitude
    r = tool_nose_radius.to("mm").magnitude
    if f <= 0:
        raise ValueError("feed must be positive")
    if r <= 0:
        raise ValueError("tool_nose_radius must be positive")
    rt_mm = f * f / (8.0 * r)
    return Quantity(magnitude=rt_mm * 1000.0, unit="micrometer")


def feed_for_surface_roughness(
    *, target_roughness: Quantity, tool_nose_radius: Quantity
) -> Quantity:
    """The feed that meets a roughness target, f = √(32·r·Ra).

    The sizing inverse of :func:`theoretical_surface_roughness`: the coarsest per-revolution feed
    that still holds a ``target_roughness`` Ra with a given ``tool_nose_radius`` r, f = √(32·r·Ra).
    Running at this feed maximizes the removal rate (productivity) without breaching the finish
    spec. Returns the feed in mm.
    """
    _check(target_roughness, "[length]", "target_roughness")
    _check(tool_nose_radius, "[length]", "tool_nose_radius")
    ra_mm = target_roughness.to("mm").magnitude
    r = tool_nose_radius.to("mm").magnitude
    if ra_mm <= 0:
        raise ValueError("target_roughness must be positive")
    if r <= 0:
        raise ValueError("tool_nose_radius must be positive")
    return Quantity(magnitude=(32.0 * r * ra_mm) ** 0.5, unit="mm")


def cutting_power(*, specific_cutting_force: Quantity, material_removal_rate: Quantity) -> Quantity:
    """The spindle power a cut demands, P_c = k_s·MRR.

    The module sizes the cut — speed, feed, depth, removal rate, tool life, finish — but never
    asked whether the machine can turn it. That is one product: the ``specific_cutting_force`` k_s,
    the energy it takes to remove unit volume of the workpiece material (≈ 2000 MPa for medium
    carbon steel, ≈ 700 for aluminium; the same material constant
    :func:`anvilate.analysis.broaching.broaching_cutting_force` already takes), times the
    ``material_removal_rate`` of :func:`material_removal_rate`.

    Pressure times volumetric flow is power — Pa·m³/s = W exactly — which is what makes this worth
    unit-checking rather than eyeballing: a 150 m/min, 0.25 mm/rev, 3 mm roughing pass in steel
    removes 112.5 cm³/min and asks 3.75 kW at the cutter, so a nominal 7.5 kW spindle at ~75%
    drive efficiency is working hard. This is power at the cut; divide by the machine's efficiency
    for what the motor must supply, and note it says nothing about torque at low spindle speeds,
    which is the other way a heavy cut stalls. Returns the cutting power in W.
    """
    _check(specific_cutting_force, "[pressure]", "specific_cutting_force")
    _check(material_removal_rate, "[volume]/[time]", "material_removal_rate")
    k_s = specific_cutting_force.to("Pa").magnitude
    mrr = material_removal_rate.to("m**3/s").magnitude
    if k_s <= 0:
        raise ValueError("specific_cutting_force must be positive")
    if mrr < 0:
        raise ValueError("material_removal_rate must be non-negative")
    return Quantity(magnitude=k_s * mrr, unit="W")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
