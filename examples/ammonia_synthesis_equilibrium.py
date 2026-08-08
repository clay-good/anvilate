"""Worked example: the equilibrium thermodynamics of ammonia synthesis.

The Haber-Bosch reaction N2 + 3H2 -> 2NH3 is exothermic and loses entropy, so whether it favors
ammonia depends sharply on temperature. Gibbs free energy decides the direction, the equilibrium
constant says how far it goes, and the van 't Hoff equation shows why running hot hurts the yield.

Using per-mole-of-reaction values ΔH = -92 kJ/mol and ΔS = -198 J/(mol·K), at 298 K the Gibbs
free-energy change is about -33 kJ/mol — spontaneous — giving an equilibrium constant of roughly
6.1e5, strongly product-favored. But heating from 298 K to 498 K collapses the constant by a factor
of about 3.3e-7 (the exothermic reaction runs backward when heated), which is why the industrial
process trades away equilibrium yield for reaction rate and recovers it with pressure. This example
reports the Gibbs free-energy change, the equilibrium constant at 298 K, and the van 't Hoff ratio.

Run it directly (``python examples/ammonia_synthesis_equilibrium.py``);
:func:`ammonia_equilibrium` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    equilibrium_constant,
    gibbs_free_energy_change,
    vant_hoff_constant_ratio,
)
from anvilate.units import Quantity

ENTHALPY_CHANGE = Quantity(magnitude=-92000.0, unit="J/mol")
ENTROPY_CHANGE = Quantity(magnitude=-198.0, unit="J/(mol*K)")
TEMPERATURE = Quantity(magnitude=298.0, unit="K")
HOT_TEMPERATURE = Quantity(magnitude=498.0, unit="K")


def ammonia_equilibrium() -> dict[str, float]:
    """Return the Gibbs free-energy change, the equilibrium constant, and the van 't Hoff ratio."""
    dg = gibbs_free_energy_change(
        enthalpy_change=ENTHALPY_CHANGE,
        temperature=TEMPERATURE,
        entropy_change=ENTROPY_CHANGE,
    )
    k = equilibrium_constant(gibbs_free_energy_change=dg, temperature=TEMPERATURE)
    ratio = vant_hoff_constant_ratio(
        enthalpy_change=ENTHALPY_CHANGE,
        temperature_low=TEMPERATURE,
        temperature_high=HOT_TEMPERATURE,
    )
    return {
        "gibbs_free_energy_kj_mol": dg.to("J/mol").magnitude / 1000.0,
        "equilibrium_constant": k,
        "vant_hoff_ratio_298_to_498": ratio,
    }


def main() -> None:
    d = ammonia_equilibrium()
    print(f"Gibbs free-energy change: {d['gibbs_free_energy_kj_mol']:.1f} kJ/mol")
    print(f"equilibrium constant at 298 K: {d['equilibrium_constant']:.3e}")
    print(f"van 't Hoff ratio (298->498 K): {d['vant_hoff_ratio_298_to_498']:.3e}")


if __name__ == "__main__":
    main()
