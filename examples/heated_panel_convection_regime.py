"""Worked example: is a heated panel's natural convection laminar or turbulent? The Rayleigh check.

Before you pick a natural-convection correlation you have to know which regime the flow is in, and
that is what the Rayleigh number tells you. This example takes a vertical panel dissipating heat
into still air, warmer than the room by 30°C, and works the two dimensionless numbers that govern
it: the Grashof number Gr = g·β·ΔT·L³/ν² (buoyancy against viscosity) and the Rayleigh number
Ra = Gr·Pr. For a short 0.3 m panel the Rayleigh number sits below the ~10⁹ transition, so the
boundary layer is laminar and the laminar correlation applies; scale the panel up to 2 m and the L³
term drives Rayleigh past 10⁹ into the turbulent range, where a different correlation (and a higher
heat-transfer rate) takes over. The lesson is that the same panel and temperature can be in either
regime depending only on its height — so check Ra before you reach for a Nusselt formula.

Run it directly (``python examples/heated_panel_convection_regime.py``);
:func:`panel_regimes` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import grashof_number, rayleigh_number
from anvilate.units import Quantity

# Air at ~300 K: beta = 1/T, kinematic viscosity, and Prandtl number.
THERMAL_EXPANSION = Quantity.parse("0.00333 1/K")
TEMPERATURE_DIFFERENCE = Quantity.parse("30 K")
KINEMATIC_VISCOSITY = Quantity.parse("1.6e-5 m**2/s")
PRANDTL = 0.71
TURBULENT_TRANSITION = 1e9


def _rayleigh(height: str) -> float:
    gr = grashof_number(
        thermal_expansion_coefficient=THERMAL_EXPANSION,
        temperature_difference=TEMPERATURE_DIFFERENCE,
        characteristic_length=Quantity.parse(height),
        kinematic_viscosity=KINEMATIC_VISCOSITY,
    )
    return rayleigh_number(grashof_number=gr, prandtl_number=PRANDTL)


def panel_regimes() -> dict[str, float]:
    """Return the Rayleigh number of a short and a tall panel."""
    return {
        "rayleigh_0p3m": _rayleigh("0.3 m"),
        "rayleigh_2m": _rayleigh("2 m"),
    }


def main() -> None:
    r = panel_regimes()
    short_regime = "laminar" if r["rayleigh_0p3m"] < TURBULENT_TRANSITION else "turbulent"
    tall_regime = "laminar" if r["rayleigh_2m"] < TURBULENT_TRANSITION else "turbulent"
    print(f"0.3 m panel : Ra = {r['rayleigh_0p3m']:.2e} ({short_regime})")
    print(f"2 m panel   : Ra = {r['rayleigh_2m']:.2e} ({tall_regime})")
    print(
        "  -> the L³ term flips the regime with height; check Ra before picking a Nusselt formula"
    )


if __name__ == "__main__":
    main()
