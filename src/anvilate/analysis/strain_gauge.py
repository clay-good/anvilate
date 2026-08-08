"""T1 analytical strain-gauge / Wheatstone-bridge checks (closed-form).

A bonded foil strain gauge turns the strain in a part into a tiny change in electrical resistance,
and a Wheatstone bridge turns that resistance change into a measurable voltage. This is the
instrumentation behind every load cell, torque sensor, and experimental stress measurement, and it
is the electrical bridge back to the mechanics the rest of the library computes: a gauge measures
the strain that Hooke's law (sigma = E * epsilon) ties to the stress a member actually carries.

The gauge factor GF relates the fractional resistance change to strain, dR/R = GF * epsilon, so a
reading inverts to epsilon = (dR/R) / GF. Wiring the gauge into a Wheatstone bridge scales the
signal by the number of active arms: the bridge output ratio is V_o/V_ex = n * GF * epsilon / 4,
with n = 1 for a quarter bridge (one active gauge), 2 for a half bridge, and 4 for a full bridge.
Reading a test therefore inverts the bridge relation, epsilon = 4 * (V_o/V_ex) / (n * GF) — more
active arms give a larger, cleaner signal for the same strain.

All quantities here are dimensionless ratios (strain, resistance change, output volts per excitation
volt, gauge factor), so they are taken and returned as plain floats.
"""

from __future__ import annotations

__all__ = [
    "gauge_strain_from_resistance",
    "strain_from_bridge_output",
    "wheatstone_bridge_output",
]

_ACTIVE_ARMS = (1, 2, 4)


def gauge_strain_from_resistance(*, resistance_change_ratio: float, gauge_factor: float) -> float:
    """The strain from a gauge's fractional resistance change, epsilon = (dR/R) / GF.

    Inverts the defining relation of a strain gauge: the mechanical strain that produced a measured
    fractional resistance change ``resistance_change_ratio`` dR/R, given the ``gauge_factor`` GF
    (about 2.0 for a standard constantan foil gauge). Returns the strain as a plain float (m/m); a
    reading of 0.002 at GF 2.0 is 0.001 = 1000 microstrain.
    """
    if gauge_factor <= 0:
        raise ValueError("gauge_factor must be positive")
    return resistance_change_ratio / gauge_factor


def wheatstone_bridge_output(*, gauge_factor: float, strain: float, active_arms: int = 1) -> float:
    """The Wheatstone-bridge output ratio, V_o/V_ex = n * GF * epsilon / 4.

    The ideal bridge output per unit excitation from a ``gauge_factor`` GF gauge set reading a
    ``strain`` epsilon, wired with ``active_arms`` n (1 = quarter, 2 = half, 4 = full bridge, each
    active arm assumed to see the full strain magnitude). Returns the output ratio V_o/V_ex as a
    plain float (volts out per volt of excitation); multiply by the excitation voltage for a signal.
    """
    if gauge_factor <= 0:
        raise ValueError("gauge_factor must be positive")
    if active_arms not in _ACTIVE_ARMS:
        raise ValueError("active_arms must be 1 (quarter), 2 (half), or 4 (full bridge)")
    return active_arms * gauge_factor * strain / 4.0


def strain_from_bridge_output(
    *, output_ratio: float, gauge_factor: float, active_arms: int = 1
) -> float:
    """The strain from a bridge reading, epsilon = 4 * (V_o/V_ex) / (n * GF).

    Inverts :func:`wheatstone_bridge_output` for the field case: the strain behind a measured
    ``output_ratio`` V_o/V_ex from a ``gauge_factor`` GF bridge of ``active_arms`` n. It is how a
    data logger's millivolt reading becomes the strain (and, via E, the stress) in the part. Returns
    the strain as a plain float (m/m).
    """
    if gauge_factor <= 0:
        raise ValueError("gauge_factor must be positive")
    if active_arms not in _ACTIVE_ARMS:
        raise ValueError("active_arms must be 1 (quarter), 2 (half), or 4 (full bridge)")
    return 4.0 * output_ratio / (active_arms * gauge_factor)
