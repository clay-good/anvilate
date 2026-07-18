"""Capstone: the long-stroke cylinder whose rod buckles before it runs out of force.

A hydraulic cylinder pushes a 50 kN load through a 1.2 m stroke: a 63 mm bore at 200 bar, a
28 mm rod. Sized on force it is comfortable -- the full bore area at 200 bar makes 62 kN, a
safety factor of 1.25 over the load -- and a force-only check calls it done. It fails anyway,
at full extension, because the thing carrying that thrust is a long thin rod.

At full stroke the piston rod is a slender column 1.2 m long carrying the cylinder's push in
pure compression, and a 28 mm rod at that length is well into the Euler regime (slenderness
ratio 171). Its buckling load is only 41 kN against the 50 kN thrust -- a safety factor of
0.83 -- so the rod bows sideways and jackknifes long before the fluid pressure is the limit.
The cylinder makes plenty of force; the rod cannot carry it standing up.

The fix is not more pressure or a bigger bore -- those only *increase* the thrust the rod must
survive. It is a *fatter rod*: growing it from 28 mm to 32 mm raises the buckling load to
71 kN (a safety factor of 1.41) with the same bore, pressure, and stroke. The lesson is that a
long-stroke cylinder has a failure mode its force calculation never sees: the rod is a column,
and at full extension it is sized by buckling, not by the force the cylinder can deliver. Check
the rod as a column whenever the stroke is long -- and remember that pushing harder makes the
buckling worse, not better.

Run it directly (``python examples/hydraulic_rod_buckling.py``);
:func:`screen_cylinder` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    circular_second_moment,
    cylinder_extend_force,
    euler_buckling_load,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

PRESSURE = Quantity.parse("20 MPa")  # 200 bar
BORE_DIAMETER = Quantity.parse("63 mm")
STROKE = Quantity.parse("1200 mm")
LOAD = Quantity.parse("50 kN")
ELASTIC_MODULUS = Quantity.parse("200 GPa")

AS_DRAWN_ROD_DIAMETER = Quantity.parse("28 mm")  # slender
STOUTER_ROD_DIAMETER = Quantity.parse("32 mm")  # the fix


def _screen(rod_diameter: Quantity) -> Scorecard:
    extend_force = cylinder_extend_force(pressure=PRESSURE, bore_diameter=BORE_DIAMETER)
    # At full extension the rod is a pinned-pinned column carrying the thrust.
    rod_second_moment = circular_second_moment(rod_diameter)
    buckling_load = euler_buckling_load(
        elastic_modulus=ELASTIC_MODULUS, second_moment=rod_second_moment, length=STROKE
    )
    load_kn = LOAD.to("kN").magnitude
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "extend force vs load",
                computed=extend_force.to("kN").magnitude / load_kn,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "rod column buckling at full stroke",
                computed=buckling_load.to("kN").magnitude / load_kn,
                required=1.0,
            ),
        )
    )


def screen_cylinder() -> Scorecard:
    """Screen the 28 mm rod: the cylinder makes the force, but the rod buckles."""
    return _screen(AS_DRAWN_ROD_DIAMETER)


def screen_stouter_rod() -> Scorecard:
    """Screen the 32 mm rod: the same bore and pressure, now the rod carries the thrust."""
    return _screen(STOUTER_ROD_DIAMETER)


def main() -> None:
    print("as drawn (28 mm rod):")
    print(screen_cylinder())
    print("\nstouter (32 mm rod):")
    print(screen_stouter_rod())


if __name__ == "__main__":
    main()
