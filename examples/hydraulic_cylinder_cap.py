"""Capstone: a hydraulic cylinder end cap, from wall to seal to bolts.

A 200-bar (20 MPa) hydraulic cylinder, 80 mm bore, is closed by a bolted end cap with an
O-ring face seal. Five subsystems all have to survive the same pressure, and they come from
five different parts of the library:

1. **Cylinder wall** -- the Lamé thick-wall bore von Mises stress against the steel's yield.
2. **End cover** -- the clamped circular cover plate's bending stress under the pressure.
3. **Seal squeeze** -- the O-ring's squeeze fraction against the static-seal floor.
4. **Seal fill** -- the O-ring gland's fill fraction against the 90 % ceiling that leaves
   room for the ring to swell.
5. **Cap bolts** -- the total bolt preload against the hydrostatic end force trying to
   blow the cap off.

Every check passes, but the margins say something a wall-thickness calculation alone would
miss. The structural parts are comfortable -- the wall sits at a safety factor of 3.1, the
cover at 2.9 -- while the *tightest* constraints are the seal and the clamping: the bolts at
1.8, the O-ring squeeze at 1.4, and the **gland fill at 1.2, the binding one**. A pressure
cap is governed by its seal and its bolts, not its wall; thickening the steel buys margin
where there is already plenty and none where it is scarce. The design is only as strong as
its worst subsystem, and here that subsystem is a groove, not a wall.

Run it directly (``python examples/hydraulic_cylinder_cap.py``);
:func:`screen_cap` is also exercised in the test suite.
"""

from __future__ import annotations

from math import pi

from anvilate.analysis import (
    clamped_circular_plate_uniform_load,
    o_ring_gland_fill_fraction,
    o_ring_squeeze_fraction,
    thick_wall_cylinder,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

PRESSURE = Quantity.parse("20 MPa")
BORE_RADIUS = Quantity.parse("40 mm")
BORE_DIAMETER = Quantity.parse("80 mm")
WALL_THICKNESS = Quantity.parse("8 mm")
COVER_THICKNESS = Quantity.parse("14 mm")
ELASTIC_MODULUS = Quantity.parse("200 GPa")
YIELD_STRENGTH = Quantity.parse("350 MPa")

O_RING_CROSS_SECTION = Quantity.parse("3.53 mm")
O_RING_GLAND_DEPTH = Quantity.parse("2.79 mm")
O_RING_GROOVE_WIDTH = Quantity.parse("4.7 mm")
MIN_SQUEEZE = 0.15
MAX_FILL = 0.90

NUMBER_OF_BOLTS = 6
BOLT_PRELOAD = Quantity.parse("30 kN")  # per bolt


def _hydrostatic_end_force() -> float:
    """The force (N) trying to lift the cap: pressure over the bore area."""
    p = PRESSURE.to("MPa").magnitude
    r = BORE_RADIUS.to("mm").magnitude
    return p * pi * r**2


def screen_cap() -> Scorecard:
    """Screen the cap across wall, cover, seal squeeze, seal fill, and cap bolts."""
    wall = thick_wall_cylinder(pressure=PRESSURE, radius=BORE_RADIUS, wall_thickness=WALL_THICKNESS)
    cover = clamped_circular_plate_uniform_load(
        pressure=PRESSURE,
        diameter=BORE_DIAMETER,
        thickness=COVER_THICKNESS,
        elastic_modulus=ELASTIC_MODULUS,
    )
    squeeze = o_ring_squeeze_fraction(
        cross_section_diameter=O_RING_CROSS_SECTION, gland_depth=O_RING_GLAND_DEPTH
    )
    fill = o_ring_gland_fill_fraction(
        cross_section_diameter=O_RING_CROSS_SECTION,
        gland_depth=O_RING_GLAND_DEPTH,
        groove_width=O_RING_GROOVE_WIDTH,
    )
    total_preload = NUMBER_OF_BOLTS * BOLT_PRELOAD.to("N").magnitude

    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "cylinder wall (bore von Mises)",
                computed=YIELD_STRENGTH.to("MPa").magnitude
                / wall.bore_von_mises_stress.to("MPa").magnitude,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "end cover bending",
                computed=YIELD_STRENGTH.to("MPa").magnitude
                / cover.max_bending_stress.to("MPa").magnitude,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "O-ring squeeze vs floor",
                computed=squeeze / MIN_SQUEEZE,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "O-ring gland fill vs ceiling",
                computed=MAX_FILL / fill,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "cap bolts vs end force",
                computed=total_preload / _hydrostatic_end_force(),
                required=1.0,
            ),
        )
    )


def main() -> None:
    print(f"hydrostatic end force: {_hydrostatic_end_force() / 1000:.1f} kN")
    print(screen_cap())


if __name__ == "__main__":
    main()
