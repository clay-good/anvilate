"""Worked example: the hoist rope that is failed by its sheave, not its load.

A workshop hoist lifts 12 kN on a 13 mm six-strand wire rope whose datasheet reads 106 kN
breaking strength -- a comfortable 8.83 against the design factor of 5 that hoisting duty
demands. Sized on the straight pull, the rope looks generous. But a rope earns its living
running over a sheave, and wrapping the sheave bends every outer wire to the sheave's
curvature: a bending stress of E_r·d_w/D that, spread over the rope's 68 mm² of metal,
acts like *extra tension* the straight-pull check never sees.

On the compact 250 mm sheave the builder prefers (barely 19 rope diameters), that
equivalent bending load is 20.3 kN -- nearly twice the payload itself. Screened against
tension plus bending, the margin collapses to 3.28 and the rope fails its design factor.
The groove agrees: the bearing pressure 2F/(d·D) runs 7.38 MPa against the 6.5 MPa the
cast-steel sheave allows (0.88), peening the groove and fatiguing the wires from outside
in. Nothing is wrong with the rope; both failures are the sheave's diameter.

Swapping to a 600 mm sheave (46 diameters) drops the bending load to 8.5 kN -- the
strength margin recovers to 5.18 -- and the groove pressure to 3.08 MPa (2.11). The
lesson is that a wire rope is rated *with its reeving*: the bending load is inverse in
the sheave diameter and can rival the payload on a small sheave, which is why rope
catalogues insist on minimum sheave-to-rope ratios. When a rope over a small sheave runs
out of margin, the fix is a bigger sheave, not a bigger rope -- a fatter rope has fatter
wires and wins back less than it adds.

Run it directly (``python examples/hoist_sheave_bending.py``);
:func:`screen_hoist` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    wire_rope_equivalent_bending_load,
    wire_rope_sheave_pressure,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

# The load and the duty.
HOIST_LOAD = Quantity.parse("12 kN")
DESIGN_FACTOR = 5.0  # hoisting duty demands a wide margin on the breaking strength

# The rope's datasheet: 13 mm six-strand steel rope.
ROPE_DIAMETER = Quantity.parse("13 mm")
OUTER_WIRE_DIAMETER = Quantity.parse("0.9 mm")
METAL_AREA = Quantity.parse("68 mm**2")
ROPE_MODULUS = Quantity.parse("83 GPa")  # effective rope modulus, well below solid steel
BREAKING_STRENGTH = Quantity.parse("106 kN")
ALLOWABLE_SHEAVE_PRESSURE = Quantity.parse("6.5 MPa")  # on a cast-steel sheave

COMPACT_SHEAVE = Quantity.parse("250 mm")  # barely 19 rope diameters
GENEROUS_SHEAVE = Quantity.parse("600 mm")  # 46 rope diameters


def _screen(sheave_diameter: Quantity) -> Scorecard:
    bending_load = wire_rope_equivalent_bending_load(
        wire_diameter=OUTER_WIRE_DIAMETER,
        sheave_diameter=sheave_diameter,
        rope_modulus=ROPE_MODULUS,
        metal_area=METAL_AREA,
    )
    total_load_n = HOIST_LOAD.to("N").magnitude + bending_load.to("N").magnitude
    pressure = wire_rope_sheave_pressure(
        tension=HOIST_LOAD,
        rope_diameter=ROPE_DIAMETER,
        sheave_diameter=sheave_diameter,
    )
    breaking_n = BREAKING_STRENGTH.to("N").magnitude
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "static rope tension vs breaking strength",
                computed=breaking_n / HOIST_LOAD.to("N").magnitude,
                required=DESIGN_FACTOR,
            ),
            ScorecardEntry.from_safety_factor(
                "tension plus sheave bending vs breaking strength",
                computed=breaking_n / total_load_n,
                required=DESIGN_FACTOR,
            ),
            ScorecardEntry.from_safety_factor(
                "sheave bearing pressure vs allowable",
                computed=ALLOWABLE_SHEAVE_PRESSURE.to("MPa").magnitude
                / pressure.to("MPa").magnitude,
                required=1.0,
            ),
        )
    )


def screen_hoist() -> Scorecard:
    """Screen the hoist on its compact 250 mm sheave: the sheave fails the rope."""
    return _screen(COMPACT_SHEAVE)


def screen_generous_sheave() -> Scorecard:
    """Screen the same rope on a 600 mm sheave: the margins recover."""
    return _screen(GENEROUS_SHEAVE)


def main() -> None:
    for name, sheave in (("compact", COMPACT_SHEAVE), ("generous", GENEROUS_SHEAVE)):
        bending = wire_rope_equivalent_bending_load(
            wire_diameter=OUTER_WIRE_DIAMETER,
            sheave_diameter=sheave,
            rope_modulus=ROPE_MODULUS,
            metal_area=METAL_AREA,
        )
        print(f"{name} {sheave} sheave: bending load {bending.to('kN').magnitude:.1f} kN")
    print("\ncompact 250 mm sheave (19 rope diameters):")
    print(screen_hoist().report())
    print("\ngenerous 600 mm sheave (46 rope diameters):")
    print(screen_generous_sheave().report())


if __name__ == "__main__":
    main()
