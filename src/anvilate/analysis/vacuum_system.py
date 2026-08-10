"""T1 analytical vacuum-system (pump-down) checks (closed-form).

Evacuating a chamber is a first-order process: a pump removes gas at a volumetric ``pumping_speed``
S, so the pressure falls exponentially with time. Ignoring leaks and outgassing, the pump-down time
from an initial pressure P₁ to a target P₂ is t = (V/S)·ln(P₁/P₂), where V is the chamber volume.
The logarithm is the key insight — each decade of pressure drop costs the same amount of time, so
reaching high vacuum takes many time constants, and the low-pressure end is where real outgassing
(not modeled here) starts to dominate.

The gas load a pump actually moves is the throughput Q = S·P, the pressure-volume flow (e.g.
mbar·L/s or Pa·m³/s) — the same physical quantity at any point in the line, which is what lets you
size a pump against a known leak or outgassing rate: the pump must provide S = Q/P at the operating
pressure P. Pumping speed, volume, and pressures are dimension-checked
:class:`~anvilate.units.Quantity` values.
"""

from __future__ import annotations

from math import log

from ..units import Quantity

__all__ = [
    "vacuum_pump_down_time",
    "vacuum_throughput",
]


def vacuum_pump_down_time(
    *,
    chamber_volume: Quantity,
    pumping_speed: Quantity,
    initial_pressure: Quantity,
    final_pressure: Quantity,
) -> Quantity:
    """The ideal pump-down time, t = (V/S)·ln(P₁/P₂).

    The time to evacuate a chamber of ``chamber_volume`` V from ``initial_pressure`` P₁ to
    ``final_pressure`` P₂ with a pump of constant ``pumping_speed`` S: t = (V/S)·ln(P₁/P₂). Pressure
    falls exponentially, so each decade costs the same (V/S)·ln(10), and V/S is the system's time
    constant. This ignores leaks and outgassing — real systems deviate at low pressure, where those
    gas loads set a floor the pump-down curve flattens toward — so treat it as an optimistic
    screening estimate. Returns the pump-down time in seconds.
    """
    _check(chamber_volume, "[volume]", "chamber_volume")
    _check(pumping_speed, "[volume]/[time]", "pumping_speed")
    _check(initial_pressure, "[pressure]", "initial_pressure")
    _check(final_pressure, "[pressure]", "final_pressure")
    v = chamber_volume.to("m**3").magnitude
    s = pumping_speed.to("m**3/s").magnitude
    p1 = initial_pressure.to("Pa").magnitude
    p2 = final_pressure.to("Pa").magnitude
    if v <= 0 or s <= 0:
        raise ValueError("chamber_volume and pumping_speed must be positive")
    if p1 <= 0 or p2 <= 0:
        raise ValueError("pressures must be positive")
    if p2 >= p1:
        raise ValueError(
            "final_pressure must be below initial_pressure (the chamber is pumped down)"
        )
    return Quantity(magnitude=v / s * log(p1 / p2), unit="s")


def vacuum_throughput(*, pumping_speed: Quantity, pressure: Quantity) -> Quantity:
    """The vacuum throughput (gas load), Q = S·P.

    The pressure-volume flow of gas a pump moves at a given operating point: the ``pumping_speed`` S
    times the ``pressure`` P, Q = S·P. Throughput is conserved along a leak-free line, so it is the
    common currency for sizing a system — a pump must supply S = Q/P at the working pressure to
    balance a known leak or outgassing load Q. Returns the throughput in Pa·m³/s (divide by the
    pressure unit to recover the familiar mbar·L/s).
    """
    _check(pumping_speed, "[volume]/[time]", "pumping_speed")
    _check(pressure, "[pressure]", "pressure")
    s = pumping_speed.to("m**3/s").magnitude
    p = pressure.to("Pa").magnitude
    if s < 0:
        raise ValueError("pumping_speed must be non-negative")
    if p < 0:
        raise ValueError("pressure must be non-negative")
    return Quantity(magnitude=s * p, unit="Pa*m**3/s")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
