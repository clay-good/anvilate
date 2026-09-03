"""Worked example: the clutch that grows plates, not spring force.

A small vehicle clutch must carry a 90 N·m engine torque with a 1.5 service factor --
135 N·m of design torque -- through friction faces bounded by a 70 mm outer and 50 mm
inner radius at a face friction of 0.3. The diaphragm spring can clamp 2 kN before the
pedal effort turns unacceptable, and that is the whole problem: a single plate gripped
on both faces (two friction surfaces) transmits only mu*F*N*r_eff = 72 N·m on the
conservative uniform-wear effective radius -- a 0.53 safety factor, barely half the
torque the engine makes.

The instinctive fix, a stiffer spring, is the wrong one: torque is linear in clamp
force, so reaching 135 N·m needs nearly double the pedal effort. The right fix is the
one every motorcycle uses -- stack plates. Torque is equally linear in the number of
friction surfaces, and surfaces are nearly free: three driven plates interleaved with
steels give six friction interfaces from the *same* 2 kN spring, and the stack carries
216 N·m -- a 1.6 safety factor -- with no change to pedal feel.

The lesson is the shape of the torque equation T = mu*F*N*r_eff (Shigley, uniform-wear
theory): of its four levers, the surface count N is the cheapest to pull. Friction
radius is boxed in by the housing, mu by the lining chemistry, and clamp force by the
operator's leg; plates just stack.

Run it directly (``python examples/multi_plate_clutch_stack.py``);
:func:`screen_single_plate_clutch` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import disc_clutch_torque
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

ENGINE_TORQUE = Quantity.parse("90 N*m")
SERVICE_FACTOR = 1.5
SPRING_FORCE = Quantity.parse("2 kN")
OUTER_RADIUS = Quantity.parse("70 mm")
INNER_RADIUS = Quantity.parse("50 mm")
FRICTION_COEFFICIENT = 0.3  # dry organic lining

SINGLE_PLATE_SURFACES = 2  # one driven plate, gripped on both faces
STACKED_SURFACES = 6  # three driven plates interleaved with steels


def _screen(surfaces: int) -> Scorecard:
    capacity = disc_clutch_torque(
        actuating_force=SPRING_FORCE,
        outer_radius=OUTER_RADIUS,
        inner_radius=INNER_RADIUS,
        friction_coefficient=FRICTION_COEFFICIENT,
        surfaces=surfaces,
        theory="uniform_wear",
    )
    design_torque = ENGINE_TORQUE.to("N*m").magnitude * SERVICE_FACTOR
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "clutch torque capacity vs design torque",
                computed=capacity.to("N*m").magnitude / design_torque,
                required=1.0,
            ),
        )
    )


def screen_single_plate_clutch() -> Scorecard:
    """Screen the single-plate clutch: the 2 kN spring cannot carry the engine."""
    return _screen(SINGLE_PLATE_SURFACES)


def screen_stacked_clutch() -> Scorecard:
    """Screen the three-plate stack: six surfaces carry the torque from the same spring."""
    return _screen(STACKED_SURFACES)


def main() -> None:
    print(f"design torque: {ENGINE_TORQUE.to('N*m').magnitude * SERVICE_FACTOR:.0f} N*m")
    print("single plate (2 surfaces):")
    print(screen_single_plate_clutch().report())
    print("\nthree-plate stack (6 surfaces):")
    print(screen_stacked_clutch().report())


if __name__ == "__main__":
    main()
