"""Worked example: the tank that could hold pressure but not vacuum.

A 1 m diameter steel tank is to be pulled down to full vacuum. The instinct is to
size it like a pressure vessel — check the wall against the hoop stress — and by
that measure a 3 mm wall is wildly overbuilt: at one atmosphere of pressure
difference it carries a hoop stress of about 17 MPa, a huge margin on steel.

That check is answering the wrong question. Under vacuum the load is *external*,
and a thin shell under external pressure does not burst — it buckles, snapping
into an oval at a pressure that scales with the cube of the wall-to-radius ratio.
The critical pressure for the 3 mm wall is only 0.012 MPa, so the tank implodes
under a tenth of one atmosphere: it collapses at 8% of the vacuum it must hold. An
8 mm wall reaches 0.225 MPa, better but still short of a 3x margin on the 0.1 MPa
external load (0.75). It takes 12 mm before the shell buckles at 0.76 MPa and
clears the margin (2.53).

External pressure is a stability problem, not a strength one, and its answer rides
on t³, not the gentle t of a hoop-stress check. A vessel safe against internal
pressure can be nowhere near safe against the same pressure applied outward.

Run it directly (``python examples/vacuum_vessel_buckling.py``);
:func:`screen_vacuum_vessel` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import cylinder_external_pressure_buckling
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

ELASTIC_MODULUS = Quantity.parse("200 GPa")
MEAN_RADIUS = Quantity.parse("500 mm")
EXTERNAL_PRESSURE = Quantity.parse("0.1 MPa")  # one atmosphere of vacuum
BUCKLING_SAFETY_FACTOR = 3.0

WALL_THICKNESSES = {
    "3 mm wall": Quantity.parse("3 mm"),
    "8 mm wall": Quantity.parse("8 mm"),
    "12 mm wall": Quantity.parse("12 mm"),
}


def screen_vacuum_vessel() -> Scorecard:
    """Screen each wall thickness: the external-pressure collapse must beat the
    vacuum load by the buckling safety factor (SF = p_cr / external / factor)."""
    external = EXTERNAL_PRESSURE.to("MPa").magnitude
    entries = []
    for name, thickness in WALL_THICKNESSES.items():
        p_cr = cylinder_external_pressure_buckling(
            elastic_modulus=ELASTIC_MODULUS, wall_thickness=thickness, mean_radius=MEAN_RADIUS
        )
        entries.append(
            ScorecardEntry.from_safety_factor(
                name,
                computed=p_cr.to("MPa").magnitude / (external * BUCKLING_SAFETY_FACTOR),
                required=1.0,
            )
        )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    for name, thickness in WALL_THICKNESSES.items():
        p_cr = cylinder_external_pressure_buckling(
            elastic_modulus=ELASTIC_MODULUS, wall_thickness=thickness, mean_radius=MEAN_RADIUS
        )
        print(f"{name}: collapse pressure {p_cr.to('MPa').magnitude:.4f} MPa")
    print(screen_vacuum_vessel())


if __name__ == "__main__":
    main()
