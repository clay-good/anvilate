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
"""

from __future__ import annotations

from ..units import Quantity

__all__ = [
    "fill_factor",
    "solar_cell_efficiency",
    "solar_cell_max_power",
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
    return p / (g * a)


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
