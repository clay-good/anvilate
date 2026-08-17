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

Sources: Duffie & Beckman, *Solar Engineering of Thermal Processes*, and
IEC 61215, for the irradiance, cell-temperature and array-yield relations.
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "pv_array_power",
    "pv_array_size_for_load",
    "pv_cell_temperature",
    "pv_daily_energy",
    "pv_fill_factor",
    "pv_temperature_derated_power",
    "pv_specific_yield",
    "pv_performance_ratio",
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


def pv_cell_temperature(
    *,
    ambient_temperature: Quantity,
    irradiance: Quantity,
    noct: Quantity,
) -> Quantity:
    """The PV cell operating temperature, T_cell = T_amb + (NOCT − 20)·G/800.

    A panel in the sun runs far hotter than the air around it, and that is what erodes its output.
    The nominal-operating-cell-temperature model estimates it from the ``ambient_temperature``
    T_amb, the plane-of-array ``irradiance`` G, and the module's ``noct`` (the cell temperature at
    800 W/m², 20 °C air, from the datasheet): T_cell = T_amb + (NOCT − 20)·G/800. Full sun on a hot
    day can put a cell 25–30 °C above ambient. Feed the result to
    :func:`pv_temperature_derated_power`. Returns the cell temperature in °C.
    """
    _check(ambient_temperature, "[temperature]", "ambient_temperature")
    _check(irradiance, "[power]/[area]", "irradiance")
    _check(noct, "[temperature]", "noct")
    t_amb = ambient_temperature.to("degC").magnitude
    g = irradiance.to("W/m**2").magnitude
    noct_c = noct.to("degC").magnitude
    if g < 0:
        raise ValueError("irradiance must be non-negative")
    return Quantity(magnitude=t_amb + (noct_c - 20.0) * g / 800.0, unit="degC")


def pv_temperature_derated_power(
    *,
    rated_power: Quantity,
    cell_temperature: Quantity,
    temperature_coefficient: float,
) -> Quantity:
    """The temperature-derated PV power, P = P_stc·[1 + γ·(T_cell − 25)].

    A module's nameplate is measured at a 25 °C cell (Standard Test Conditions), but a real cell
    runs hotter and makes less power. The derated output is
    P = ``rated_power``·[1 + γ·(``cell_temperature`` − 25)], where the ``temperature_coefficient`` γ
    of power is the datasheet value — negative, about −0.003 to −0.005 per °C for silicon. A cell at
    60 °C loses roughly 12–17% against its nameplate,
    which is why a rooftop array's summer output falls short of its rating even in full sun. Returns
    the derated power in W.
    """
    _check(rated_power, "[power]", "rated_power")
    _check(cell_temperature, "[temperature]", "cell_temperature")
    p_stc = rated_power.to("W").magnitude
    t_cell = cell_temperature.to("degC").magnitude
    if p_stc <= 0:
        raise ValueError("rated_power must be positive")
    factor = 1.0 + temperature_coefficient * (t_cell - 25.0)
    if factor < 0:
        raise ValueError("temperature_coefficient and cell_temperature give a non-physical power")
    return Quantity(magnitude=p_stc * factor, unit="W")


def pv_specific_yield(*, energy: Quantity, rated_power: Quantity) -> Quantity:
    """A PV system's specific (final) yield, Y_f = E/P_rated.

    The energy a PV system produces per unit of its rated (nameplate) DC power over a period:
    Y_f = ``energy`` E / ``rated_power`` P_rated (the IEC 61724 final yield). Reported in kWh/kWp,
    it is dimensionally a time — the number of hours the array would need to run at full nameplate
    power to make the same energy — so a site with 1600 kWh/kWp per year yields the equivalent of
    1600 full-power hours. It normalizes production across system sizes for comparison. Returns the
    specific yield in hours (numerically kWh/kWp).
    """
    _check(energy, "[energy]", "energy")
    _check(rated_power, "[power]", "rated_power")
    e = energy.to("kWh").magnitude
    p = rated_power.to("kW").magnitude
    if e < 0:
        raise ValueError("energy must be non-negative")
    if p <= 0:
        raise ValueError("rated_power must be positive")
    return Quantity(magnitude=e / p, unit="hour")


def pv_performance_ratio(
    *,
    energy: Quantity,
    rated_power: Quantity,
    peak_sun_hours: Quantity,
) -> float:
    """A PV system's performance ratio, PR = E/(P_rated·H).

    The quality metric that grades a real PV plant against its ideal potential: PR =
    ``energy`` E / (``rated_power`` P_rated · ``peak_sun_hours`` H), where H is the in-plane
    irradiation expressed as equivalent hours at 1000 W/m² (the reference yield). Equivalently it is
    the specific yield over the reference yield. PR strips out the resource so only the losses
    remain — soiling, temperature, wiring, inverter, downtime — so a well-run plant sits at
    0.75–0.85 regardless of how sunny its site is. Returns the dimensionless performance ratio.
    """
    _check(energy, "[energy]", "energy")
    _check(rated_power, "[power]", "rated_power")
    _check(peak_sun_hours, "[time]", "peak_sun_hours")
    e = energy.to("kWh").magnitude
    p = rated_power.to("kW").magnitude
    h = peak_sun_hours.to("hour").magnitude
    if e < 0:
        raise ValueError("energy must be non-negative")
    if p <= 0:
        raise ValueError("rated_power must be positive")
    if h <= 0:
        raise ValueError("peak_sun_hours must be positive")
    return e / (p * h)


def pv_fill_factor(
    *,
    maximum_power: Quantity,
    open_circuit_voltage: Quantity,
    short_circuit_current: Quantity,
) -> float:
    """A solar cell's fill factor, FF = P_max/(V_oc·I_sc).

    How square a photovoltaic cell's current-voltage curve is, and with it the cell's quality: the
    ``maximum_power`` P_max at the maximum-power point over the product of the
    ``open_circuit_voltage`` V_oc and ``short_circuit_current`` I_sc, FF = P_max/(V_oc·I_sc). V_oc
    and I_sc bound the I-V curve, and FF is the fraction of that bounding rectangle the operating
    point actually reaches — a good crystalline-silicon cell sits at 0.75–0.82, and series
    resistance or recombination pulls it down. It ties the cell efficiency to the three measured
    terminal quantities. Returns the dimensionless fill factor (0 to 1).
    """
    _check(maximum_power, "[power]", "maximum_power")
    _check(open_circuit_voltage, "[electric_potential]", "open_circuit_voltage")
    _check(short_circuit_current, "[current]", "short_circuit_current")
    p_max = maximum_power.to("W").magnitude
    v_oc = open_circuit_voltage.to("V").magnitude
    i_sc = short_circuit_current.to("A").magnitude
    if p_max <= 0:
        raise ValueError("maximum_power must be positive")
    if v_oc <= 0:
        raise ValueError("open_circuit_voltage must be positive")
    if i_sc <= 0:
        raise ValueError("short_circuit_current must be positive")
    ff = p_max / (v_oc * i_sc)
    if ff > 1.0:
        raise ValueError(
            "maximum_power exceeds V_oc·I_sc (fill factor > 1 is impossible); check inputs"
        )
    return ff


def _fraction(value: float, name: str) -> None:
    if not 0.0 < value <= 1.0:
        raise ValueError(f"{name} must be in (0, 1]; got {value}")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
