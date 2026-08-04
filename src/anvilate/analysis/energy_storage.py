"""T1 analytical battery / backup-power sizing checks (closed-form).

Sizing a UPS, solar, or telecom battery bank is a small chain of relations around one idea: only
part of a battery's nameplate capacity is usable, and the design must carry the load through the
outage on that part.

A bank's required capacity follows from the load it must hold and for how long: C = P·t/(V·DoD·η),
where P is the load power, t the autonomy (backup) time, V the DC system voltage, DoD the usable
depth of discharge (you never fully drain a battery — a fraction is held back for cycle life), and η
the round-trip/inverter efficiency. Turned around, a given bank's usable energy is
E = C·V·DoD·η, and the time it can carry a load is that energy over the load power.

Depth of discharge and efficiency are the caller's values, read from the battery datasheet and the
system design; the sizing here is the arithmetic that ties them to a runtime.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "battery_backup_time",
    "battery_bank_capacity",
    "usable_battery_energy",
]


def battery_bank_capacity(
    *,
    load_power: Quantity,
    autonomy_time: Quantity,
    system_voltage: Quantity,
    depth_of_discharge: float,
    efficiency: float,
) -> Quantity:
    """The battery capacity a backup load needs, C = P·t/(V·DoD·η).

    The amp-hour capacity to carry a ``load_power`` P through an ``autonomy_time`` t at a DC
    ``system_voltage`` V: C = P·t/(V·DoD·η), discounted by the usable ``depth_of_discharge`` DoD
    (the fraction of the nameplate you actually draw) and the ``efficiency`` η (inverter and
    round-trip losses). Both are dimensionless in (0, 1]. Returns the required capacity in
    amp-hours.
    """
    _check(load_power, "[power]", "load_power")
    _check(autonomy_time, "[time]", "autonomy_time")
    _check(system_voltage, "[electric_potential]", "system_voltage")
    _fraction(depth_of_discharge, "depth_of_discharge")
    _fraction(efficiency, "efficiency")
    if load_power.to("W").magnitude <= 0:
        raise ValueError("load_power must be positive")
    if autonomy_time.to("s").magnitude <= 0:
        raise ValueError("autonomy_time must be positive")
    if system_voltage.to("V").magnitude <= 0:
        raise ValueError("system_voltage must be positive")
    energy = load_power.pint * autonomy_time.pint
    capacity = energy / (system_voltage.pint * depth_of_discharge * efficiency)
    return Quantity(magnitude=float(capacity.to("A*hour").magnitude), unit="A*hour")


def usable_battery_energy(
    *,
    rated_capacity: Quantity,
    system_voltage: Quantity,
    depth_of_discharge: float,
    efficiency: float,
) -> Quantity:
    """The energy a bank can actually deliver, E = C·V·DoD·η.

    A battery's nameplate is amp-hours at its DC voltage, but only the usable fraction reaches the
    load: E = C·V·DoD·η, from the ``rated_capacity`` C, the ``system_voltage`` V, the usable
    ``depth_of_discharge`` DoD, and the delivery ``efficiency`` η. Returns the deliverable energy in
    watt-hours.
    """
    _check(rated_capacity, "[current]*[time]", "rated_capacity")
    _check(system_voltage, "[electric_potential]", "system_voltage")
    _fraction(depth_of_discharge, "depth_of_discharge")
    _fraction(efficiency, "efficiency")
    if rated_capacity.to("A*hour").magnitude <= 0:
        raise ValueError("rated_capacity must be positive")
    if system_voltage.to("V").magnitude <= 0:
        raise ValueError("system_voltage must be positive")
    energy = rated_capacity.pint * system_voltage.pint * depth_of_discharge * efficiency
    return Quantity(magnitude=float(energy.to("W*hour").magnitude), unit="W*hour")


def battery_backup_time(
    *,
    rated_capacity: Quantity,
    system_voltage: Quantity,
    load_power: Quantity,
    depth_of_discharge: float,
    efficiency: float,
) -> Quantity:
    """The runtime a bank gives a load, t = C·V·DoD·η/P (the sizing inverse).

    How long a bank of ``rated_capacity`` C at ``system_voltage`` V can carry a ``load_power`` P:
    t = C·V·DoD·η/P, its usable energy over the load — the inverse of
    :func:`battery_bank_capacity`. ``depth_of_discharge`` DoD and ``efficiency`` η are the usable
    fraction and the delivery efficiency. Returns the backup time in hours.
    """
    _check(load_power, "[power]", "load_power")
    if load_power.to("W").magnitude <= 0:
        raise ValueError("load_power must be positive")
    energy = usable_battery_energy(
        rated_capacity=rated_capacity,
        system_voltage=system_voltage,
        depth_of_discharge=depth_of_discharge,
        efficiency=efficiency,
    )
    time = energy.pint / load_power.pint
    return Quantity(magnitude=float(time.to("hour").magnitude), unit="hour")


def _fraction(value: float, name: str) -> None:
    if not 0.0 < value <= 1.0:
        raise ValueError(f"{name} must be in (0, 1]; got {value}")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
