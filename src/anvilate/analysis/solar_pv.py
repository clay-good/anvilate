"""T1 analytical solar-PV array sizing checks (closed-form).

Sizing a photovoltaic array is a short chain from sunlight to delivered energy, and pairs with
:mod:`anvilate.analysis.energy_storage` to size an off-grid system end to end.

A module's power is what its area collects at the reference irradiance times how efficiently it
converts it: P = G·A·η, from the plane-of-array irradiance G (1000 W/m² at standard test
conditions), the module ``area`` A, and the ``module_efficiency`` η.

The energy an array yields over a day is not its rated power times 24 hours — the sun is neither
full nor overhead all day. The site's *peak sun hours* PSH (the day's insolation expressed as hours
at 1000 W/m²) collapse that into E = P·PSH·D, with a derate factor D for the real-world losses
(inverter, wiring, soiling, temperature, typically ~0.75–0.8). Turned around, the array a daily
energy demand needs is P = E/(PSH·D).

Peak sun hours, module efficiency, and the derate factor are the caller's site and equipment values;
the sizing arithmetic is here.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "pv_array_power",
    "pv_array_size_for_load",
    "pv_daily_energy",
]


def pv_array_power(
    *,
    irradiance: Quantity,
    area: Quantity,
    module_efficiency: float,
) -> Quantity:
    """The electrical power a PV module or array produces, P = G·A·η.

    A module collects the ``irradiance`` G falling on its ``area`` A and converts a fraction
    ``module_efficiency`` η of it: P = G·A·η. At standard test conditions G = 1000 W/m², so a 1.6 m²
    module at 20% efficiency is rated 320 W. η is dimensionless in (0, 1]. Returns the power in
    watts.
    """
    _check(irradiance, "[power]/[length]**2", "irradiance")
    _check(area, "[length]**2", "area")
    _fraction(module_efficiency, "module_efficiency")
    g = irradiance.to("W/m**2").magnitude
    a = area.to("m**2").magnitude
    if g <= 0 or a <= 0:
        raise ValueError("irradiance and area must be positive")
    return Quantity(magnitude=g * a * module_efficiency, unit="W")


def pv_daily_energy(
    *,
    rated_power: Quantity,
    peak_sun_hours: Quantity,
    derate_factor: float,
) -> Quantity:
    """The energy a PV array yields in a day, E = P·PSH·D.

    The daily energy is the ``rated_power`` P times the site's ``peak_sun_hours`` PSH (the day's
    insolation expressed as equivalent hours at 1000 W/m²) times a ``derate_factor`` D for inverter,
    wiring, soiling, and temperature losses (typically ~0.75–0.8): E = P·PSH·D. Returns the daily
    energy in kilowatt-hours.
    """
    _check(rated_power, "[power]", "rated_power")
    _check(peak_sun_hours, "[time]", "peak_sun_hours")
    _fraction(derate_factor, "derate_factor")
    if rated_power.to("W").magnitude <= 0:
        raise ValueError("rated_power must be positive")
    if peak_sun_hours.to("hour").magnitude <= 0:
        raise ValueError("peak_sun_hours must be positive")
    energy = rated_power.pint * peak_sun_hours.pint * derate_factor
    return Quantity(magnitude=float(energy.to("kWh").magnitude), unit="kWh")


def pv_array_size_for_load(
    *,
    daily_energy_demand: Quantity,
    peak_sun_hours: Quantity,
    derate_factor: float,
) -> Quantity:
    """The array rating a daily load needs, P = E/(PSH·D) (the sizing inverse).

    The rated power to meet a ``daily_energy_demand`` E at a site of ``peak_sun_hours`` PSH, after a
    ``derate_factor`` D for real-world losses: P = E/(PSH·D) — the inverse of
    :func:`pv_daily_energy`. Returns the required array rating in watts.
    """
    _check(daily_energy_demand, "[energy]", "daily_energy_demand")
    _check(peak_sun_hours, "[time]", "peak_sun_hours")
    _fraction(derate_factor, "derate_factor")
    if daily_energy_demand.to("kWh").magnitude <= 0:
        raise ValueError("daily_energy_demand must be positive")
    if peak_sun_hours.to("hour").magnitude <= 0:
        raise ValueError("peak_sun_hours must be positive")
    power = daily_energy_demand.pint / (peak_sun_hours.pint * derate_factor)
    return Quantity(magnitude=float(power.to("W").magnitude), unit="W")


def _fraction(value: float, name: str) -> None:
    if not 0.0 < value <= 1.0:
        raise ValueError(f"{name} must be in (0, 1]; got {value}")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
