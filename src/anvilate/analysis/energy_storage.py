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

Sources: IEC 61427 and standard battery-engineering practice (Peukert's
relation, C-rate and round-trip efficiency) as given in Linden's *Handbook of Batteries*.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "battery_backup_time",
    "battery_bank_capacity",
    "battery_delivered_energy",
    "battery_round_trip_efficiency",
    "c_rate",
    "current_from_c_rate",
    "discharge_time_from_c_rate",
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


def battery_round_trip_efficiency(
    *,
    energy_discharged: Quantity,
    energy_charged: Quantity,
) -> float:
    """The battery round-trip efficiency, η = E_out/E_in.

    Storing energy and getting it back is lossy — the charge and discharge each waste some to
    internal resistance and, in a lead-acid cell, to gassing. The round-trip efficiency is the ratio
    of the ``energy_discharged`` E_out returned to the ``energy_charged`` E_in put in over a full
    cycle: η = E_out/E_in. Lithium-ion reaches ~0.90–0.95, lead-acid ~0.75–0.85, flow batteries
    lower. It is what turns a nameplate storage capacity into the energy a system can actually count
    on (see :func:`battery_delivered_energy`). Returns the dimensionless efficiency (0 to 1).
    """
    _check(energy_discharged, "[energy]", "energy_discharged")
    _check(energy_charged, "[energy]", "energy_charged")
    e_out = energy_discharged.to("J").magnitude
    e_in = energy_charged.to("J").magnitude
    if e_out < 0 or e_in <= 0:
        raise ValueError("energy_charged must be positive and energy_discharged non-negative")
    if e_out > e_in:
        raise ValueError("energy_discharged cannot exceed energy_charged (η > 1 is impossible)")
    return e_out / e_in


def battery_delivered_energy(
    *,
    stored_energy: Quantity,
    round_trip_efficiency: float,
) -> Quantity:
    """The energy a battery actually returns, E_out = E_stored·η.

    The usable energy that comes back out of storage after the round-trip losses: the
    ``stored_energy`` E_stored (what went in, e.g. a day's solar surplus) times the
    ``round_trip_efficiency`` η (from :func:`battery_round_trip_efficiency` or the datasheet).
    Sizing an off-grid or backup system on the stored energy alone overstates what the loads will
    see by the loss fraction — a 10 kWh charge through an 0.9 battery delivers only 9 kWh. Returns
    the delivered energy in kWh.
    """
    _check(stored_energy, "[energy]", "stored_energy")
    _fraction(round_trip_efficiency, "round_trip_efficiency")
    e = stored_energy.to("kWh").magnitude
    if e < 0:
        raise ValueError("stored_energy must be non-negative")
    return Quantity(magnitude=e * round_trip_efficiency, unit="kWh")


def c_rate(*, current: Quantity, capacity: Quantity) -> float:
    """The battery C-rate, C-rate = I/C.

    The charge or discharge current normalized to the cell's capacity: C-rate = I/C, from the
    ``current`` I and the amp-hour ``capacity`` C. A rate of 1C drains (or fills) the pack in one
    hour, 0.5C in two, 2C in half an hour — it is how battery currents are quoted independent of
    pack size, and it sets the heating and voltage sag a cell sees. (The *actual* runtime falls
    short of the ideal 1/C-rate hours at high rates; the Peukert relations of
    :mod:`anvilate.analysis.battery_peukert` capture that derating.) Returns the C-rate as a plain
    float, in units of 1/hour (a "1C" rate returns 1.0).
    """
    _check(current, "[current]", "current")
    _check(capacity, "[current]*[time]", "capacity")
    i = current.to("A").magnitude
    cap = capacity.to("A*hour").magnitude
    if i < 0:
        raise ValueError("current must be non-negative")
    if cap <= 0:
        raise ValueError("capacity must be positive")
    return i / cap


def current_from_c_rate(*, c_rate: float, capacity: Quantity) -> Quantity:
    """The current at a given C-rate, I = C-rate·C.

    The charge or discharge current a chosen ``c_rate`` draws from a pack of amp-hour ``capacity``
    C: I = C-rate·C — the inverse of :func:`c_rate`. A 100 Ah pack at 0.5C delivers 50 A; at 2C it
    must push 200 A, which is what sizes the cabling, contactors, and BMS current limit. Returns the
    current in amperes.
    """
    _check(capacity, "[current]*[time]", "capacity")
    cap = capacity.to("A*hour").magnitude
    if c_rate < 0:
        raise ValueError("c_rate must be non-negative")
    if cap <= 0:
        raise ValueError("capacity must be positive")
    return Quantity(magnitude=c_rate * cap, unit="A")


def discharge_time_from_c_rate(*, c_rate: float) -> Quantity:
    """The ideal discharge time from a C-rate, t = 1/C-rate.

    The time a pack lasts at a steady ``c_rate``, on the nameplate assumption that usable capacity
    is rate-independent: t = 1/C-rate hours. A 0.5C draw runs two hours, a 2C draw half an hour. It
    is the first-cut runtime a designer quotes; at high rates the deliverable capacity shrinks
    (Peukert effect, :func:`anvilate.analysis.battery_peukert.peukert_runtime`), so treat this as an
    optimistic upper bound. Returns the discharge time in hours.
    """
    if c_rate <= 0:
        raise ValueError("c_rate must be positive")
    return Quantity(magnitude=1.0 / c_rate, unit="hour")


def _fraction(value: float, name: str) -> None:
    if not 0.0 < value <= 1.0:
        raise ValueError(f"{name} must be in (0, 1]; got {value}")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
