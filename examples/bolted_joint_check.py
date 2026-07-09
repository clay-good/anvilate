"""Worked example: a T1 screening of a bolted lap joint, end to end.

Runs the deterministic vertical with no LLM: an M8 bolt clamps two steel plates
in a lap joint that transfers an 8 kN transverse load. It develops the bolt
preload from the tightening torque, then screens the two joint failure modes —
bearing on the plate and shear across the bolt — against material strengths
pulled from the standards database, rolling the results into a scorecard.

Run it directly (``python examples/bolted_joint_check.py``);
:func:`screen_bolted_joint` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    bearing_stress,
    bolt_preload_from_torque,
    bolt_shear_stress,
    strength_scorecard,
)
from anvilate.scorecard import Scorecard
from anvilate.standards import default_materials_db
from anvilate.units import Quantity

BOLT_DIAMETER = Quantity.parse("8 mm")
TRANSFERRED_LOAD = Quantity.parse("8 kN")


def screen_bolted_joint() -> Scorecard:
    """Screen the example M8 lap joint and return the rolled-up scorecard."""
    db = default_materials_db()
    plate = db.get("ASTM-A36")  # the plates
    bolt = db.get("AISI-4140")  # a medium-strength bolt

    # Bearing: the bolt crushing the 6 mm plate, screened against the plate yield.
    bearing = bearing_stress(
        force=TRANSFERRED_LOAD, diameter=BOLT_DIAMETER, thickness=Quantity.parse("6 mm")
    )
    bearing_check = strength_scorecard(
        "plate bearing",
        stress=bearing,
        allowable=plate.yield_strength.quantity,
        required=1.5,
    )

    # Shear across the bolt (single shear), screened against the bolt's shear
    # yield ~ 0.577 * Sy (distortion-energy).
    shear = bolt_shear_stress(force=TRANSFERRED_LOAD, diameter=BOLT_DIAMETER)
    bolt_sy = bolt.yield_strength.quantity.to("MPa").magnitude
    shear_yield = Quantity(magnitude=0.577 * bolt_sy, unit="MPa")
    shear_check = strength_scorecard(
        "bolt shear",
        stress=shear,
        allowable=shear_yield,
        required=1.5,
    )
    return Scorecard(entries=(bearing_check, shear_check))


def main() -> None:
    # The tightening torque develops a preload (reported, not scored here).
    preload = bolt_preload_from_torque(
        torque=Quantity.parse("20 N*m"), nominal_diameter=BOLT_DIAMETER
    )
    print(f"bolt preload from 20 N*m: {preload.to('kN')}")
    card = screen_bolted_joint()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
