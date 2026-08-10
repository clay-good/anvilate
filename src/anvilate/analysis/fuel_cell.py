"""T1 analytical fuel-cell performance checks (closed-form).

A fuel cell converts a fuel's chemical energy straight into electricity, and unlike a heat engine it
is not bound by the Carnot limit — its ceiling is thermodynamic, set by the reaction's free energy.
Three closed-form relations frame that ceiling and how far a real cell falls below it.

The reversible (open-circuit) cell voltage comes from the Gibbs free energy released per mole of
reaction, E_rev = −ΔG/(n·F), where n is the electrons transferred per reaction and F is the Faraday
constant. For the hydrogen-oxygen cell (ΔG = −237 kJ/mol, n = 2) this is the familiar 1.23 V.

The thermodynamic (maximum) efficiency is the fraction of the fuel's total enthalpy that is
available as electrical work, η_max = ΔG/ΔH — about 0.83 for hydrogen on a higher-heating-value
basis, the fuel-cell analog of the Carnot efficiency. A real cell loses more to activation,
ohmic, and mass-transport polarization, which drop the operating voltage below E_rev; the voltage
efficiency η_V = V_cell/E_rev captures that loss, and the cell's overall efficiency is the product
of the thermodynamic and voltage efficiencies (times any fuel-utilization factor). Free energies and
enthalpies are molar, dimension-checked :class:`~anvilate.units.Quantity` values; efficiencies are
plain floats.
"""

from __future__ import annotations

from ..units import Quantity

_FARADAY = 96485.33212  # C/mol, Faraday constant

__all__ = [
    "reversible_cell_voltage",
    "thermodynamic_efficiency",
    "voltage_efficiency",
]


def reversible_cell_voltage(
    *, gibbs_free_energy_change: Quantity, electrons_transferred: int
) -> Quantity:
    """The reversible cell voltage, E_rev = −ΔG/(n·F).

    The open-circuit voltage a fuel cell (or any electrochemical cell) develops at equilibrium, from
    the molar Gibbs free energy of reaction ``gibbs_free_energy_change`` ΔG (negative for a
    spontaneous cell) and the ``electrons_transferred`` n per reaction: E_rev = −ΔG/(n·F) with the
    Faraday constant F. For the H2/O2 cell (ΔG = −237 kJ/mol, n = 2) it is 1.23 V. It is the
    standard potential E0 that :func:`anvilate.analysis.nernst.nernst_potential` then shifts for
    off-standard concentrations, and the ceiling the operating voltage sits below. Returns the
    reversible voltage in volts.
    """
    _check(gibbs_free_energy_change, "[energy]/[substance]", "gibbs_free_energy_change")
    if not isinstance(electrons_transferred, int) or electrons_transferred < 1:
        raise ValueError("electrons_transferred must be an integer of at least 1")
    dg = gibbs_free_energy_change.to("J/mol").magnitude
    if dg >= 0:
        raise ValueError(
            "gibbs_free_energy_change must be negative (a spontaneous cell); got "
            f"{gibbs_free_energy_change}"
        )
    return Quantity(magnitude=-dg / (electrons_transferred * _FARADAY), unit="V")


def thermodynamic_efficiency(
    *, gibbs_free_energy_change: Quantity, enthalpy_change: Quantity
) -> float:
    """The fuel-cell thermodynamic efficiency, η_max = ΔG/ΔH.

    The largest fraction of a fuel's reaction enthalpy that a cell can deliver as electrical work:
    the molar Gibbs free energy ``gibbs_free_energy_change`` ΔG over the molar reaction
    ``enthalpy_change`` ΔH (both negative for an exothermic, spontaneous reaction), η_max = ΔG/ΔH.
    For hydrogen it is ~0.83 (HHV) — higher than a comparable heat engine's Carnot limit, which is
    the thermodynamic case for fuel cells. Because ΔG = ΔH − T·ΔS, a reaction with rising entropy
    can even exceed 1. Returns the dimensionless thermodynamic efficiency.
    """
    _check(gibbs_free_energy_change, "[energy]/[substance]", "gibbs_free_energy_change")
    _check(enthalpy_change, "[energy]/[substance]", "enthalpy_change")
    dg = gibbs_free_energy_change.to("J/mol").magnitude
    dh = enthalpy_change.to("J/mol").magnitude
    if dh == 0:
        raise ValueError("enthalpy_change must be non-zero")
    if dg > 0 or dh > 0:
        raise ValueError("ΔG and ΔH must be negative (a spontaneous, exothermic reaction)")
    return dg / dh


def voltage_efficiency(*, cell_voltage: Quantity, reversible_voltage: Quantity) -> float:
    """The fuel-cell voltage efficiency, η_V = V_cell/E_rev.

    How much of the reversible voltage survives the cell's polarization losses: the operating
    ``cell_voltage`` V_cell (under load) over the ``reversible_voltage`` E_rev (from
    :func:`reversible_cell_voltage`), η_V = V_cell/E_rev. Activation, ohmic, and mass-transport
    overpotentials pull the voltage down as current is drawn, so η_V falls with load; a cell running
    at 0.7 V against a 1.23 V reversible potential has η_V ≈ 0.57. Multiplying it by the
    thermodynamic efficiency (:func:`thermodynamic_efficiency`) gives the cell's overall
    energy efficiency. Returns the dimensionless voltage efficiency (0 to 1).
    """
    _check(cell_voltage, "[electric_potential]", "cell_voltage")
    _check(reversible_voltage, "[electric_potential]", "reversible_voltage")
    v = cell_voltage.to("V").magnitude
    e_rev = reversible_voltage.to("V").magnitude
    if e_rev <= 0:
        raise ValueError("reversible_voltage must be positive")
    if v < 0:
        raise ValueError("cell_voltage must be non-negative")
    if v > e_rev:
        raise ValueError("cell_voltage cannot exceed reversible_voltage (η_V > 1 is impossible)")
    return v / e_rev


def _check(value: Quantity, expected: str, name: str) -> None:
    if not value.has_dimension(expected):
        raise ValueError(
            f"{name} must be a {expected} quantity; got {value.dimensionality} ({value})"
        )
