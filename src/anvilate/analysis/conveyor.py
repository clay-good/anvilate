"""T1 analytical belt-conveyor (bulk-material handling) checks (closed-form).

A belt conveyor carries bulk solids — ore, grain, aggregate — and it is a different machine from the
power-transmission belts of :mod:`anvilate.analysis.belt`: there the belt transmits torque between
pulleys, here it carries a load along its length. Sizing one turns on two things: how much material
it moves, and how much power it takes to lift that material.

The throughput is how much material rides the belt and how fast it goes: the mass flow rate is
ṁ = ρ·A·v, the bulk density ρ times the cross-sectional area A of the load profile on the belt (set
by the belt width and the trough angle) times the belt speed v. Turned around, the belt speed a
target throughput needs is v = ṁ/(ρ·A) — the sizing inverse that, against a maximum sensible belt
speed, decides the belt width.

The power splits into moving the belt and load along (friction, which needs the conveyor's length
and a friction factor) and lifting the material through any rise. The lift term is the clean,
dominant one on an inclined conveyor: P = ṁ·g·H raises a mass flow ṁ through a height H, and unlike
the friction term it is irreducible — the rate of gaining potential energy, a floor on drive power.

Sources: CEMA, *Belt Conveyors for Bulk Materials* — the mass flow a belt carries at a loading
and speed, the speed a capacity requires, and the power the lift alone demands.
"""

from __future__ import annotations

from ..units import Quantity

_GRAVITY = 9.80665  # m/s^2, standard gravity

__all__ = [
    "belt_speed_for_capacity",
    "conveyor_lift_power",
    "conveyor_mass_flow",
]


def conveyor_mass_flow(
    *,
    bulk_density: Quantity,
    cross_section_area: Quantity,
    belt_speed: Quantity,
) -> Quantity:
    """The conveyor mass flow rate, ṁ = ρ·A·v.

    How much bulk material a belt carries per unit time, from the ``bulk_density`` ρ of the load,
    the ``cross_section_area`` A of the load profile riding on the belt (set by the belt width and
    the trough angle), and the ``belt_speed`` v: ṁ = ρ·A·v. This is the throughput a conveyor is
    rated by, usually quoted in tonnes per hour. Returns the mass flow rate in kg/s.
    """
    _check(bulk_density, "[mass]/[length]**3", "bulk_density")
    _check(cross_section_area, "[area]", "cross_section_area")
    _check(belt_speed, "[length]/[time]", "belt_speed")
    rho = bulk_density.to("kg/m**3").magnitude
    a = cross_section_area.to("m**2").magnitude
    v = belt_speed.to("m/s").magnitude
    if rho <= 0 or a <= 0:
        raise ValueError("bulk_density and cross_section_area must be positive")
    if v < 0:
        raise ValueError("belt_speed must be non-negative")
    return Quantity(magnitude=rho * a * v, unit="kg/s")


def belt_speed_for_capacity(
    *,
    mass_flow: Quantity,
    bulk_density: Quantity,
    cross_section_area: Quantity,
) -> Quantity:
    """The belt speed a target throughput needs, v = ṁ/(ρ·A) (the sizing inverse).

    The belt speed to carry a required ``mass_flow`` ṁ of a material of ``bulk_density`` ρ over a
    load profile of ``cross_section_area`` A: v = ṁ/(ρ·A), the inverse of
    :func:`conveyor_mass_flow`. Checked against a maximum sensible belt speed (too fast spills and
    wears), this is what decides the belt width — a wider belt carries the load at a lower, kinder
    speed. Returns the required belt speed in m/s.
    """
    _check(mass_flow, "[mass]/[time]", "mass_flow")
    _check(bulk_density, "[mass]/[length]**3", "bulk_density")
    _check(cross_section_area, "[area]", "cross_section_area")
    m = mass_flow.to("kg/s").magnitude
    rho = bulk_density.to("kg/m**3").magnitude
    a = cross_section_area.to("m**2").magnitude
    if m < 0:
        raise ValueError("mass_flow must be non-negative")
    if rho <= 0 or a <= 0:
        raise ValueError("bulk_density and cross_section_area must be positive")
    return Quantity(magnitude=m / (rho * a), unit="m/s")


def conveyor_lift_power(*, mass_flow: Quantity, lift_height: Quantity) -> Quantity:
    """The power to lift the material, P = ṁ·g·H.

    The drive power that goes purely into raising the load on an inclined conveyor: a ``mass_flow``
    ṁ lifted through a ``lift_height`` H gains potential energy at a rate P = ṁ·g·H. Unlike the
    friction power (which depends on the run length and a friction factor), the lift power is
    irreducible — it is the floor on the drive power of any conveyor that gains elevation, and on a
    steep lift it dominates. A downhill conveyor instead regenerates this power. Returns the lift
    power in kW.
    """
    _check(mass_flow, "[mass]/[time]", "mass_flow")
    _check(lift_height, "[length]", "lift_height")
    m = mass_flow.to("kg/s").magnitude
    h = lift_height.to("m").magnitude
    if m < 0:
        raise ValueError("mass_flow must be non-negative")
    if h < 0:
        raise ValueError("lift_height must be non-negative")
    return Quantity(magnitude=m * _GRAVITY * h / 1000.0, unit="kW")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not isinstance(value, Quantity):
        raise ValueError(f"{name} must be a {expected} quantity; got {value!r}")
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
