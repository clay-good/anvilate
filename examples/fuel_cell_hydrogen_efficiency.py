"""Worked example: how efficient a hydrogen fuel cell really is.

A hydrogen-oxygen fuel cell running to liquid water releases ΔG = -237 kJ/mol of free energy and
ΔH = -286 kJ/mol of total enthalpy (higher heating value), transferring n = 2 electrons per
reaction. Those numbers alone fix the cell's ceiling and let us grade a real one running at 0.70 V.

The reversible voltage is E_rev = -ΔG/(n·F) = 1.23 V — the familiar open-circuit potential. The
thermodynamic ceiling is η_max = ΔG/ΔH = 0.83, notably higher than a comparable heat engine's Carnot
limit, which is the whole thermodynamic appeal of fuel cells. A cell held at 0.70 V under load has a
voltage efficiency η_V = 0.70/1.23 = 0.57, so its overall energy efficiency is η_max·η_V ≈ 0.47 —
about what a good PEM stack delivers.

Run it directly (``python examples/fuel_cell_hydrogen_efficiency.py``);
:func:`hydrogen_cell_efficiency` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    reversible_cell_voltage,
    thermodynamic_efficiency,
    voltage_efficiency,
)
from anvilate.units import Quantity

GIBBS = Quantity.parse("-237 kJ/mol")
ENTHALPY = Quantity.parse("-286 kJ/mol")
ELECTRONS = 2
OPERATING_VOLTAGE = Quantity.parse("0.70 V")


def hydrogen_cell_efficiency() -> dict[str, float]:
    """Return the reversible voltage (V) and the thermodynamic, voltage, and overall efficiency."""
    e_rev = reversible_cell_voltage(gibbs_free_energy_change=GIBBS, electrons_transferred=ELECTRONS)
    eta_thermo = thermodynamic_efficiency(gibbs_free_energy_change=GIBBS, enthalpy_change=ENTHALPY)
    eta_v = voltage_efficiency(cell_voltage=OPERATING_VOLTAGE, reversible_voltage=e_rev)
    return {
        "reversible_voltage_v": e_rev.to("V").magnitude,
        "thermodynamic_efficiency": eta_thermo,
        "voltage_efficiency": eta_v,
        "overall_efficiency": eta_thermo * eta_v,
    }


def main() -> None:
    d = hydrogen_cell_efficiency()
    print("Hydrogen PEM cell at 0.70 V (HHV basis):")
    print(f"  reversible voltage    : {d['reversible_voltage_v']:.3f} V")
    print(f"  thermodynamic max η   : {d['thermodynamic_efficiency']:.3f}")
    print(f"  voltage efficiency    : {d['voltage_efficiency']:.3f}")
    print(f"  overall efficiency    : {d['overall_efficiency']:.3f}")


if __name__ == "__main__":
    main()
