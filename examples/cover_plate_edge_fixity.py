"""Worked example: the plate edge that decides a cover, not its thickness.

A round steel cover plate, 500 mm across and 10 mm thick, takes a 10 kN load pushed
on its centre by a strut. The plate must not deflect more than 1 mm at the middle,
or the strut's alignment is lost. Whether it clears that limit turns not on the
thickness -- fixed here -- but on how the rim is held.

A cover simply resting on its seat and bolted lightly is *simply supported*: its edge
can rotate, so the plate dishes freely and its centre drops 1.72 mm -- past the limit.
Weld or stiffly bolt the same plate all around and its edge is *clamped*: the fixed
rim resists the dishing, and the centre drops only 0.68 mm, comfortably inside. The
clamped plate is 2.5 times stiffer than the simply-supported one under the identical
load and thickness -- the ratio (3+nu)/(1+nu) that falls straight out of the plate
equations -- purely because of what happens at its edge.

The lesson is that a plate's boundary is a load-path decision as consequential as its
thickness. Reaching for a thicker plate is the obvious move when a cover deflects too
far; fixing its edge is often the cheaper one, and here it is the difference between
pass and fail. The plate geometry and load are declared inline.

Run it directly (``python examples/cover_plate_edge_fixity.py``);
:func:`screen_cover_plate` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    clamped_circular_plate_center_load_deflection,
    simply_supported_circular_plate_center_load_deflection,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

FORCE = Quantity.parse("10 kN")
DIAMETER = Quantity.parse("500 mm")
THICKNESS = Quantity.parse("10 mm")
ELASTIC_MODULUS = Quantity.parse("200 GPa")
DEFLECTION_LIMIT = Quantity.parse("1.0 mm")


def screen_cover_plate() -> Scorecard:
    """Screen the centre deflection against the 1 mm limit for a simply-supported and
    a clamped edge (safety factor = limit / deflection)."""
    kw = {
        "force": FORCE,
        "diameter": DIAMETER,
        "thickness": THICKNESS,
        "elastic_modulus": ELASTIC_MODULUS,
    }
    limit = DEFLECTION_LIMIT.to("mm").magnitude
    simply_supported = (
        simply_supported_circular_plate_center_load_deflection(**kw).to("mm").magnitude
    )
    clamped = clamped_circular_plate_center_load_deflection(**kw).to("mm").magnitude
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "simply-supported edge", computed=limit / simply_supported, required=1.0
            ),
            ScorecardEntry.from_safety_factor(
                "clamped edge", computed=limit / clamped, required=1.0
            ),
        )
    )


def main() -> None:
    kw = {
        "force": FORCE,
        "diameter": DIAMETER,
        "thickness": THICKNESS,
        "elastic_modulus": ELASTIC_MODULUS,
    }
    ss = simply_supported_circular_plate_center_load_deflection(**kw)
    clamped = clamped_circular_plate_center_load_deflection(**kw)
    print(f"simply-supported centre deflection: {ss.to('mm').magnitude:.2f} mm")
    print(f"clamped centre deflection:          {clamped.to('mm').magnitude:.2f} mm")
    print(screen_cover_plate())


if __name__ == "__main__":
    main()
