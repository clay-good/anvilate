"""Worked example: the helix angle that overran the thrust bearing.

A helical gear transmits 5 kN of tangential load and runs smoother and quieter
than a spur gear because its teeth engage gradually. That smoothness has a price
paid at the shaft ends: the slanted teeth shove the gear sideways along its axis
with a thrust W_a = W_t*tan(psi), and a thrust bearing has to take it.

The steeper the helix, the smoother the mesh and the larger the thrust. This shaft
carries a thrust bearing rated to 3 kN, and good practice keeps a 1.5x margin on
it. A shallow 15 degree helix throws only 1.34 kN of thrust, a comfortable 2.24
margin. Open the helix to 30 degrees for a smoother mesh and the thrust climbs to
2.89 kN — a 1.04 margin, under the 1.5 the bearing wants. A 45 degree helix, the
smoothest of the three, drives the full 5 kN straight into a 3 kN bearing (0.60):
it overloads.

The helix angle is not a free smoothness dial; every degree of it lands on the
thrust bearing. Keep the helix shallow enough for the bearing you have, size a
bigger thrust bearing, or cancel the thrust entirely with a double-helical
(herringbone) gear. The bearing rating is manufacturer's data, declared inline
like any allowable.

Run it directly (``python examples/helical_gear_thrust_bearing.py``);
:func:`screen_helical_thrust` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import helical_gear_axial_thrust
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

TANGENTIAL_LOAD = Quantity.parse("5000 N")
THRUST_BEARING_RATING = Quantity.parse("3000 N")
MIN_SAFETY_FACTOR = 1.5

HELIX_ANGLES = {
    "15 deg helix": 15.0,
    "30 deg helix": 30.0,
    "45 deg helix": 45.0,
}


def screen_helical_thrust() -> Scorecard:
    """Screen each helix angle: the thrust bearing rating over the axial thrust
    must clear the 1.5x margin (safety factor = rating / thrust)."""
    rating = THRUST_BEARING_RATING.to("N").magnitude
    entries = []
    for name, helix_angle in HELIX_ANGLES.items():
        thrust = helical_gear_axial_thrust(tangential_load=TANGENTIAL_LOAD, helix_angle=helix_angle)
        entries.append(
            ScorecardEntry.from_safety_factor(
                name, computed=rating / thrust.to("N").magnitude, required=MIN_SAFETY_FACTOR
            )
        )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    for name, helix_angle in HELIX_ANGLES.items():
        thrust = helical_gear_axial_thrust(tangential_load=TANGENTIAL_LOAD, helix_angle=helix_angle)
        print(f"{name}: axial thrust {thrust.to('N').magnitude:.0f} N")
    print(screen_helical_thrust())


if __name__ == "__main__":
    main()
