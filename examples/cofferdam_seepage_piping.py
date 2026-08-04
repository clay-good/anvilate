"""Worked example: the excavation you can pump dry but whose floor still boils.

Digging below the water table behind sheet piles raises two questions, and the obvious one is the
easy one. Yes, water seeps in and has to be pumped out — Darcy's law sizes that flow, and for a
modest excavation it is a small pump. The dangerous question is what the upward seepage does to
the soil at the bottom of the cut: as water exits the ground there, it drags on the grains, and
if the exit gradient approaches the critical gradient the soil loses all strength, boils, and the
excavation floor fails — a piping failure that has drowned cofferdams. This example computes the
seepage inflow (the pump duty) and then the factor of safety against piping at the toe. The pump
is trivial; the piping margin is thin, and it is the piping check, not the pump, that decides
whether the sheet piles have to go deeper.

Run it directly (``python examples/cofferdam_seepage_piping.py``);
:func:`seepage_check` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    critical_hydraulic_gradient,
    darcy_seepage_flow,
    piping_factor_of_safety,
)
from anvilate.units import Quantity

PERMEABILITY = Quantity.parse("1e-4 m/s")  # silty sand
AVERAGE_GRADIENT = 0.30  # driving the inflow
SEEPAGE_AREA = Quantity.parse("50 m**2")  # gross area water crosses into the cut

SPECIFIC_GRAVITY = 2.65  # quartz sand solids
VOID_RATIO = 0.70
EXIT_GRADIENT = 0.50  # upward gradient at the excavation floor
PIPING_FS_TARGET = 2.5


def seepage_check() -> dict[str, float]:
    """Return the seepage inflow (L/s), the critical gradient, and the piping factor of safety."""
    inflow = (
        darcy_seepage_flow(
            permeability=PERMEABILITY,
            hydraulic_gradient=AVERAGE_GRADIENT,
            area=SEEPAGE_AREA,
        )
        .to("m**3/s")
        .magnitude
    )
    i_cr = critical_hydraulic_gradient(specific_gravity=SPECIFIC_GRAVITY, void_ratio=VOID_RATIO)
    fs = piping_factor_of_safety(critical_gradient=i_cr, exit_gradient=EXIT_GRADIENT)
    return {
        "inflow_lps": inflow * 1000.0,
        "critical_gradient": i_cr,
        "piping_fs": fs,
    }


def main() -> None:
    s = seepage_check()
    print(f"seepage inflow    : {s['inflow_lps']:.1f} L/s  (an easy pump duty)")
    print(f"critical gradient : {s['critical_gradient']:.2f}")
    verdict = "OK" if s["piping_fs"] >= PIPING_FS_TARGET else "TOO LOW — deepen the sheet piles"
    print(f"piping FS         : {s['piping_fs']:.2f} vs {PIPING_FS_TARGET} target  ({verdict})")
    print("  -> the pump is trivial; the piping margin is what governs the design")


if __name__ == "__main__":
    main()
