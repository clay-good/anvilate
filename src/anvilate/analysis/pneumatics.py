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
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "air_receiver_holdup_time",
    "air_receiver_volume_for_demand",
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


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
