"""T1 analytical solar-cell (photovoltaic) I-V characterization checks (closed-form).

A solar cell's quality is read from its current-voltage curve: it delivers no power at open circuit
(all voltage, no current) or at short circuit (all current, no voltage), and the most power in
between. Three numbers capture the cell — the fill factor (how square the curve is), the maximum
power it produces, and the conversion efficiency. This is the cell-level characterization behind the
array-level power and sizing of :mod:`anvilate.analysis.solar_pv`, which works from a panel's rated
output rather than its I-V curve.

The fill factor FF = (V_mp*I_mp)/(V_oc*I_sc) compares the maximum-power rectangle to the product of
the open-circuit voltage V_oc and short-circuit current I_sc — 0.7-0.85 for good silicon, lower when
series resistance rounds the knee. The maximum power is then P_max = FF*V_oc*I_sc, and the
efficiency is eta = P_max/(irradiance*area), the fraction of incident sunlight the cell turns into
electricity (about 15-22% for commercial silicon at 1000 W/m^2).

All three take V_oc as given. It follows in closed form from the cell's own diode: at open circuit
the photocurrent recirculates through the junction, giving V_oc = (n*k*T/q)*ln(I_L/I_0 + 1) — a
logarithm in the light and a falling function of temperature, which is why a panel loses voltage on
a hot roof.
"""

from __future__ import annotations

from math import log

from ..units import Quantity

_BOLTZMANN = 1.380649e-23  # J/K
_ELEMENTARY_CHARGE = 1.602176634e-19  # C

__all__ = [
    "fill_factor",
    "solar_cell_efficiency",
    "solar_cell_max_power",
    "solar_cell_open_circuit_voltage",
]


def fill_factor(
    *,
    max_power_voltage: Quantity,
    max_power_current: Quantity,
    open_circuit_voltage: Quantity,
    short_circuit_current: Quantity,
) -> float:
    """The solar-cell fill factor, FF = (V_mp*I_mp)/(V_oc*I_sc).

    How square the I-V curve is: the maximum-power point (``max_power_voltage`` V_mp times
    ``max_power_current`` I_mp) over the product of the ``open_circuit_voltage`` V_oc and
    ``short_circuit_current`` I_sc. A high fill factor (0.7-0.85 for good silicon) means a sharp
    knee and low internal loss; series resistance and recombination drag it down. Returns FF as a
    float in (0, 1).
    """
    _check(max_power_voltage, "[electric_potential]", "max_power_voltage")
    _check(max_power_current, "[current]", "max_power_current")
    _check(open_circuit_voltage, "[electric_potential]", "open_circuit_voltage")
    _check(short_circuit_current, "[current]", "short_circuit_current")
    v_mp = max_power_voltage.to("V").magnitude
    i_mp = max_power_current.to("A").magnitude
    v_oc = open_circuit_voltage.to("V").magnitude
    i_sc = short_circuit_current.to("A").magnitude
    if v_mp <= 0 or i_mp <= 0:
        raise ValueError("max-power voltage and current must be positive")
    if v_oc <= 0 or i_sc <= 0:
        raise ValueError("open-circuit voltage and short-circuit current must be positive")
    if v_mp > v_oc:
        raise ValueError("max_power_voltage cannot exceed open_circuit_voltage")
    if i_mp > i_sc:
        raise ValueError("max_power_current cannot exceed short_circuit_current")
    return (v_mp * i_mp) / (v_oc * i_sc)


def solar_cell_max_power(
    *,
    open_circuit_voltage: Quantity,
    short_circuit_current: Quantity,
    fill_factor: float,
) -> Quantity:
    """The maximum cell power, P_max = FF*V_oc*I_sc.

    The peak power a cell delivers, from its ``open_circuit_voltage`` V_oc,
    ``short_circuit_current`` I_sc, and ``fill_factor`` FF: P_max = FF*V_oc*I_sc. It equals
    V_mp*I_mp at the maximum-power point, the operating point a maximum-power-point tracker holds.
    Returns the power in W.
    """
    _check(open_circuit_voltage, "[electric_potential]", "open_circuit_voltage")
    _check(short_circuit_current, "[current]", "short_circuit_current")
    v_oc = open_circuit_voltage.to("V").magnitude
    i_sc = short_circuit_current.to("A").magnitude
    if v_oc <= 0 or i_sc <= 0:
        raise ValueError("open-circuit voltage and short-circuit current must be positive")
    if not 0.0 < fill_factor <= 1.0:
        raise ValueError("fill_factor must be in (0, 1]")
    return Quantity(magnitude=fill_factor * v_oc * i_sc, unit="W")


def solar_cell_efficiency(
    *, max_power: Quantity, irradiance: Quantity, cell_area: Quantity
) -> float:
    """The solar-cell conversion efficiency, eta = P_max/(irradiance*area).

    The fraction of incident sunlight a cell converts to electricity: the ``max_power`` P_max over
    the incident power, which is the ``irradiance`` (about 1000 W/m^2 at standard test conditions)
    times the ``cell_area``. Commercial silicon reaches about 15-22%. Returns the efficiency as a
    plain float in (0, 1).
    """
    _check(max_power, "[power]", "max_power")
    _check(irradiance, "[power]/[area]", "irradiance")
    _check(cell_area, "[area]", "cell_area")
    p = max_power.to("W").magnitude
    g = irradiance.to("W/m**2").magnitude
    a = cell_area.to("m**2").magnitude
    if p < 0:
        raise ValueError("max_power must be non-negative")
    if g <= 0:
        raise ValueError("irradiance must be positive")
    if a <= 0:
        raise ValueError("cell_area must be positive")
    # The incident power is formed right here, so the first-law ceiling costs one
    # comparison. Without it a transcription slip returned 50.0 — 5000% conversion — and
    # the plausible-looking version, 1.2346, is a 123% cell reported as a bare float that
    # downstream code reads as a fraction. The cross-module twin `pv_fill_factor` already
    # applies exactly this ceiling.
    incident = g * a
    if p > incident:
        raise ValueError(
            f"max_power ({p:.4g} W) exceeds the incident power on the cell "
            f"({incident:.4g} W = {g:.4g} W/m² x {a:.4g} m²), giving an efficiency of "
            f"{p / incident:.4g}. A cell cannot deliver more than it receives; check the "
            f"cell area and the units of the power figure"
        )
    return p / incident


def solar_cell_open_circuit_voltage(
    *,
    photocurrent: Quantity,
    saturation_current: Quantity,
    temperature: Quantity,
    ideality_factor: float = 1.0,
) -> Quantity:
    """A solar cell's open-circuit voltage, V_oc = (n·k·T/q)·ln(I_L/I₀ + 1).

    V_oc feeds every function in this module and none of them could produce it. It is not an
    independent property: at open circuit the photocurrent has nowhere to go but back through the
    cell's own diode, and the voltage that forces that balance is
    V_oc = (n·k·T/q)·ln(``photocurrent`` I_L/``saturation_current`` I₀ + 1), with n the
    ``ideality_factor`` and k·T/q the thermal voltage of
    :func:`anvilate.analysis.diode.thermal_voltage` at absolute ``temperature`` T.

    The logarithm is why V_oc barely moves with light: ten times the irradiance buys only
    n·k·T/q·ln10 ≈ 60 mV per decade, which is why a panel's voltage is nearly constant through
    the day while its current tracks the sun. Temperature is the opposite story and the one that
    matters in the field — I₀ climbs so steeply with T that V_oc *falls* about 2 mV/K, so a hot
    roof costs real output, and the sign of that coefficient is the single most-missed fact in
    array sizing. Temperature must be absolute. Returns the open-circuit voltage in V.
    """
    _check(photocurrent, "[current]", "photocurrent")
    _check(saturation_current, "[current]", "saturation_current")
    _check(temperature, "[temperature]", "temperature")
    i_l = photocurrent.to("A").magnitude
    i_0 = saturation_current.to("A").magnitude
    t = temperature.to("K").magnitude
    if i_l <= 0:
        raise ValueError("photocurrent must be positive")
    if i_0 <= 0:
        raise ValueError("saturation_current must be positive")
    if t <= 0:
        raise ValueError("temperature must be a positive absolute temperature")
    if ideality_factor <= 0:
        raise ValueError("ideality_factor must be positive")
    thermal_voltage = _BOLTZMANN * t / _ELEMENTARY_CHARGE
    return Quantity(magnitude=ideality_factor * thermal_voltage * log(i_l / i_0 + 1.0), unit="V")


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
