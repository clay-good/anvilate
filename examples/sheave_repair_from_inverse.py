"""Worked example: a failing check that repairs itself in one step.

Most validators tell you a check failed and leave you to guess the fix. When the
failing check has a paired *design inverse*, the scorecard can do better: it can
name the parameter to change, the direction, and the exact value that lands the
check at the required margin -- a single solve, not a search.

A workshop hoist runs a 13 mm steel rope, 106 kN breaking strength, on a 12 kN
lift. Against the design factor of 5 that hoisting duty demands, the straight
pull sits at 8.83 -- comfortably clear, and in fact *over* the 5.0-7.0 band the
shop targets for rope, so it lands as an OVER MARGIN warning: the rope is heavier
than pure tension needs. Yet the assembly still fails, because a rope earns its
keep bending over a sheave. Wrapping the compact 250 mm sheave drives the wire
bending stress E_r*d_w/D to 298.8 MPa against a 220 MPa fatigue allowable -- a
safety factor of 0.74. The rope is fine; the sheave is too small.

The bending check is paired with :func:`minimum_sheave_diameter_for_bending_stress`,
so the failing entry carries a typed repair hint: *increase the sheave diameter to
509 mm*. Applying that one value -- no iteration -- lands the bending check at
exactly 1.50, and the assembly clears. Because the inverse targets the margin and
not one micron more, the bending check still governs, now sitting exactly at its
limit; the only remaining flag is the over-heavy rope, a warning that never blocks.

Run it directly (``python examples/sheave_repair_from_inverse.py``);
:func:`screen_on_compact_sheave` and :func:`repaired_scorecard` are exercised in
the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    minimum_sheave_diameter_for_bending_stress,
    wire_rope_bending_stress,
)
from anvilate.scorecard import Direction, RepairHint, Scorecard, ScorecardEntry
from anvilate.units import Quantity

# The load and the duty.
HOIST_LOAD = Quantity.parse("12 kN")
DESIGN_FACTOR = 5.0  # hoisting duty demands a wide margin on the breaking strength
STATIC_BAND_TOP = 7.0  # above this, the rope is heavier than pure tension needs

# The rope's datasheet: 13 mm six-strand steel rope over a cast-steel sheave.
OUTER_WIRE_DIAMETER = Quantity.parse("0.9 mm")
ROPE_MODULUS = Quantity.parse("83 GPa")  # effective rope modulus, well below solid steel
BREAKING_STRENGTH = Quantity.parse("106 kN")
ALLOWABLE_BENDING_STRESS = Quantity.parse("220 MPa")  # a fatigue-rated reeving allowable
REQUIRED_BENDING_SF = 1.5

COMPACT_SHEAVE = Quantity.parse("250 mm")  # barely 19 rope diameters -- too small


def _bending_safety_factor(sheave_diameter: Quantity) -> float:
    stress = wire_rope_bending_stress(
        wire_diameter=OUTER_WIRE_DIAMETER,
        sheave_diameter=sheave_diameter,
        rope_modulus=ROPE_MODULUS,
    )
    return ALLOWABLE_BENDING_STRESS.to("MPa").magnitude / stress.to("MPa").magnitude


def corrective_sheave_diameter() -> Quantity:
    """The sheave the design inverse solves for: bending SF back to the minimum.

    The allowable is derated by the required safety factor so the inverse targets
    the margin, not the bare allowable -- the value the repair hint carries.
    """
    derated = Quantity(
        magnitude=ALLOWABLE_BENDING_STRESS.magnitude / REQUIRED_BENDING_SF,
        unit="MPa",
    )
    return minimum_sheave_diameter_for_bending_stress(
        wire_diameter=OUTER_WIRE_DIAMETER,
        rope_modulus=ROPE_MODULUS,
        allowable_bending_stress=derated,
    )


def _screen(sheave_diameter: Quantity) -> Scorecard:
    static_sf = BREAKING_STRENGTH.to("N").magnitude / HOIST_LOAD.to("N").magnitude
    bending_sf = _bending_safety_factor(sheave_diameter)

    bending_hint = None
    if bending_sf < REQUIRED_BENDING_SF:
        # The failing check names its own repair: the inverse gives the exact
        # sheave diameter that lands the margin, in one solve.
        d_fix = corrective_sheave_diameter()
        bending_hint = RepairHint.solved(
            "sheave_diameter",
            direction=Direction.INCREASE,
            value=d_fix.to("mm").magnitude,
            unit="mm",
            provenance="minimum_sheave_diameter_for_bending_stress",
        )

    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "static rope tension vs breaking strength",
                computed=static_sf,
                required=DESIGN_FACTOR,
                upper=STATIC_BAND_TOP,  # a two-sided band: flag an over-heavy rope
            ),
            ScorecardEntry.from_safety_factor(
                "wire bending over the sheave",
                computed=bending_sf,
                required=REQUIRED_BENDING_SF,
                repair_hint=bending_hint,
            ),
        )
    )


def screen_on_compact_sheave() -> Scorecard:
    """Screen the hoist on its 250 mm sheave: the sheave fails the rope, and the
    failing bending check carries the sheave diameter that would fix it."""
    return _screen(COMPACT_SHEAVE)


def repaired_scorecard() -> Scorecard:
    """Apply the failing check's own repair hint -- one solve -- and re-screen."""
    card = screen_on_compact_sheave()
    hint = {e.name: e.repair_hint for e in card.entries}["wire bending over the sheave"]
    assert hint is not None and hint.corrective_value is not None
    return _screen(Quantity(magnitude=hint.corrective_value, unit="mm"))


def main() -> None:
    print("On the compact 250 mm sheave:")
    before = screen_on_compact_sheave()
    print(before)
    for entry in before.entries:
        print(f"  {entry}")
        if entry.repair_hint is not None:
            print(f"    -> repair: {entry.repair_hint}")
    governing = before.governing()
    print(f"  governing: {governing.name} (utilization {governing.utilization:.2f})")

    print("\nApplying the repair hint (one solve, no iteration):")
    after = repaired_scorecard()
    print(after)
    for entry in after.entries:
        print(f"  {entry}")
    shift = after.governing_shift(before)
    if shift is not None:
        print(f"  {shift}")


if __name__ == "__main__":
    main()
