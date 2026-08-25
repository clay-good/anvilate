"""T1 analytical compressed-air system checks (receiver sizing, closed-form).

Every compressed-air system has a receiver — a tank that rides out the gap between what the
compressor delivers steadily and what the tools demand in bursts. Its job is to hold enough stored
air that a peak draw does not pull the line pressure below the usable minimum before the
compressor catches up. By Boyle's law the free air a receiver of volume V gives up as its pressure
falls from p_max to p_min is V·(p_max − p_min)/p_atm, so the time it can cover a net demand Q_net
(the demand beyond the compressor's output) is

    t = V·(p_max − p_min) / (Q_net · p_atm),

and inverting it sizes the receiver for a required hold-up. Pressures enter as a band, so gauge or
absolute give the same result; the free-air flow and atmospheric pressure set the reference. Inputs
and outputs are dimension-checked :class:`~anvilate.units.Quantity` values.

Sources: Esposito, *Fluid Power with Applications* (pneumatics) — the holdup time an air
receiver gives at a stated demand, the receiver volume a demand requires, and the free air a
cylinder consumes per stroke and per minute.
"""

from __future__ import annotations

from math import pi

from ..units import Quantity
from ..units.rotation import count_rate_per_second

_STANDARD_ATMOSPHERE_PA = 101325.0

__all__ = [
    "air_receiver_holdup_time",
    "air_receiver_volume_for_demand",
    "cylinder_air_consumption_per_stroke",
    "cylinder_free_air_demand",
]


def air_receiver_holdup_time(
    *,
    receiver_volume: Quantity,
    max_pressure: Quantity,
    min_pressure: Quantity,
    net_demand: Quantity,
    atmospheric_pressure: Quantity,
) -> Quantity:
    """The time a receiver can supply a net air demand before its pressure falls to the minimum.

    How long the stored air lasts when the tools draw more than the compressor delivers:
    t = V·(p_max − p_min)/(Q_net·p_atm). ``receiver_volume`` V is the tank volume, ``max_pressure``
    and ``min_pressure`` bracket the usable pressure band, ``net_demand`` Q_net is the free-air draw
    beyond the compressor's steady output, and ``atmospheric_pressure`` p_atm sets the free-air
    reference. Returns the hold-up time in seconds.
    """
    _check(receiver_volume, "[length]**3", "receiver_volume")
    _check(max_pressure, "[pressure]", "max_pressure")
    _check(min_pressure, "[pressure]", "min_pressure")
    _check(net_demand, "[length]**3/[time]", "net_demand")
    _check(atmospheric_pressure, "[pressure]", "atmospheric_pressure")
    v = receiver_volume.to("m**3").magnitude
    p_max = max_pressure.to("Pa").magnitude
    p_min = min_pressure.to("Pa").magnitude
    q = net_demand.to("m**3/s").magnitude
    p_atm = atmospheric_pressure.to("Pa").magnitude
    if v <= 0 or q <= 0 or p_atm <= 0:
        raise ValueError("receiver_volume, net_demand, and atmospheric_pressure must be positive")
    if p_max <= p_min:
        raise ValueError("max_pressure must exceed min_pressure")
    return Quantity(magnitude=v * (p_max - p_min) / (q * p_atm), unit="s")


def air_receiver_volume_for_demand(
    *,
    net_demand: Quantity,
    holdup_time: Quantity,
    max_pressure: Quantity,
    min_pressure: Quantity,
    atmospheric_pressure: Quantity,
) -> Quantity:
    """The receiver volume a required hold-up time needs (the sizing inverse).

    The inverse of :func:`air_receiver_holdup_time`, V = Q_net·t·p_atm/(p_max − p_min) — the tank
    size that lets a compressed-air system ride out a ``net_demand`` Q_net for ``holdup_time`` t
    while the pressure drifts from ``max_pressure`` to ``min_pressure``. ``atmospheric_pressure``
    p_atm sets the free-air reference. Returns the required receiver volume in m³.
    """
    _check(net_demand, "[length]**3/[time]", "net_demand")
    _check(holdup_time, "[time]", "holdup_time")
    _check(max_pressure, "[pressure]", "max_pressure")
    _check(min_pressure, "[pressure]", "min_pressure")
    _check(atmospheric_pressure, "[pressure]", "atmospheric_pressure")
    q = net_demand.to("m**3/s").magnitude
    t = holdup_time.to("s").magnitude
    p_max = max_pressure.to("Pa").magnitude
    p_min = min_pressure.to("Pa").magnitude
    p_atm = atmospheric_pressure.to("Pa").magnitude
    if q <= 0 or t <= 0 or p_atm <= 0:
        raise ValueError("net_demand, holdup_time, and atmospheric_pressure must be positive")
    if p_max <= p_min:
        raise ValueError("max_pressure must exceed min_pressure")
    return Quantity(magnitude=q * t * p_atm / (p_max - p_min), unit="m**3")


def cylinder_air_consumption_per_stroke(
    *,
    bore_diameter: Quantity,
    stroke: Quantity,
    gauge_supply_pressure: Quantity,
    atmospheric_pressure: Quantity | None = None,
) -> Quantity:
    """The free air a pneumatic cylinder uses per stroke, V = (π/4)·D²·L·(p_g + p_atm)/p_atm.

    A cylinder does not consume the swept volume of compressed air but the far larger *free*
    (atmospheric) volume squeezed into it: by Boyle's law the swept volume (π/4)·``bore_diameter``
    D²·``stroke`` L, filled to the absolute supply pressure p_g + p_atm, expands to
    (π/4)·D²·L·(p_g + p_atm)/p_atm at atmosphere. From the ``gauge_supply_pressure`` p_g and the
    ``atmospheric_pressure`` p_atm (default one standard atmosphere), it is the number a compressor
    is sized against — a 7-bar cylinder eats about 8× its swept volume in free air. Returns the free
    air per single stroke in litres.
    """
    _check(bore_diameter, "[length]", "bore_diameter")
    _check(stroke, "[length]", "stroke")
    _check(gauge_supply_pressure, "[pressure]", "gauge_supply_pressure")
    d = bore_diameter.to("m").magnitude
    length = stroke.to("m").magnitude
    p_g = gauge_supply_pressure.to("Pa").magnitude
    if atmospheric_pressure is None:
        p_atm = _STANDARD_ATMOSPHERE_PA
    else:
        _check(atmospheric_pressure, "[pressure]", "atmospheric_pressure")
        p_atm = atmospheric_pressure.to("Pa").magnitude
    if d <= 0:
        raise ValueError("bore_diameter must be positive")
    if length <= 0:
        raise ValueError("stroke must be positive")
    if p_g <= 0:
        raise ValueError("gauge_supply_pressure must be positive")
    if p_atm <= 0:
        raise ValueError("atmospheric_pressure must be positive")
    swept = pi / 4.0 * d**2 * length
    free_air = swept * (p_g + p_atm) / p_atm
    return Quantity(magnitude=free_air * 1000.0, unit="liter")


def cylinder_free_air_demand(
    *,
    bore_diameter: Quantity,
    stroke: Quantity,
    gauge_supply_pressure: Quantity,
    cycle_rate: Quantity,
    double_acting: bool = True,
    atmospheric_pressure: Quantity | None = None,
) -> Quantity:
    """The free-air demand rate of a cycling pneumatic cylinder, Q = n_str·V_stroke·f.

    The steady free-air flow a compressor must supply to keep a cylinder cycling: the per-stroke
    consumption of :func:`cylinder_air_consumption_per_stroke` times the ``cycle_rate`` f (full
    cycles per unit time), times the number of pressurized strokes per cycle — 2 for a
    ``double_acting`` cylinder (both extend and retract draw air), 1 for a single-acting one (only
    extend; a spring returns it). From the ``bore_diameter`` D, ``stroke`` L, the
    ``gauge_supply_pressure`` p_g, and ``atmospheric_pressure`` p_atm (default 1 atm). This is the
    sizing load a compressor and its receiver are matched to. Returns the free-air demand in L/min.
    """
    per_stroke = cylinder_air_consumption_per_stroke(
        bore_diameter=bore_diameter,
        stroke=stroke,
        gauge_supply_pressure=gauge_supply_pressure,
        atmospheric_pressure=atmospheric_pressure,
    )
    _check(cycle_rate, "1/[time]", "cycle_rate")
    f = 60.0 * count_rate_per_second(cycle_rate, name="cycle_rate")
    if f <= 0:
        raise ValueError("cycle_rate must be positive")
    strokes_per_cycle = 2.0 if double_acting else 1.0
    return Quantity(
        magnitude=per_stroke.to("liter").magnitude * strokes_per_cycle * f, unit="liter/min"
    )


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
