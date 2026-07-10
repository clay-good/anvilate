"""Worked example: the speed-up nobody re-screened.

A cam-follower return spring (music wire, d = 4 mm on a 32 mm mean coil,
C = 8, ten active coils) holds the follower with ~232 N at working height.
The wire stress is Wahl-corrected 350 MPa against a 700 MPa spec-sheet
allowable — SF 2.0, and NOTHING about it changes when production wants the
machine at 1200 rpm instead of 300: same lift, same force, same stress. What
changes is the mode the static screen cannot see: the coil itself is a
fixed-fixed elastic rod that surges at f₁ = ½·√(k/m) = 139.7 Hz on its own
99 g. At 300 rpm (5 Hz) that is 28 cam orders away and the classic 15×
margin passes; at 1200 rpm (20 Hz) the floor moves to 300 Hz and the same
spring FAILs — the 7th harmonic of the lift curve lands on the coil mode and
the follower floats. The fix is a stiffer-lighter coil (or a nested pair),
not thicker wire: force never was the problem.

Run it directly (``python examples/cam_return_spring.py``);
:func:`screen_cam_return_spring` is also exercised in the test suite.
"""

from __future__ import annotations

from math import pi

from anvilate.analysis import (
    frequency_scorecard,
    helical_spring_rate,
    spring_shear_stress,
    spring_surge_frequency,
    strength_scorecard,
)
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

WIRE = Quantity.parse("4 mm")
COIL = Quantity.parse("32 mm")  # mean coil diameter, C = 8
ACTIVE_COILS = 10
SHEAR_MODULUS = Quantity.parse("79.3 GPa")  # music wire (Shigley Table 10-5)
WIRE_DENSITY = 7850.0  # kg/m^3
WORKING_DEFLECTION = Quantity.parse("30 mm")
SHEAR_ALLOWABLE = Quantity.parse("700 MPa")  # wire spec sheet, torsional
REQUIRED_SF = 1.5
CAM_SPEEDS_RPM = (300.0, 1200.0)
SURGE_MARGIN = 15.0  # keep the coil mode >= 15 cam orders up (Shigley)


def screen_cam_return_spring() -> Scorecard:
    """Screen the spring's wire stress once and its surge at both cam speeds."""
    rate = helical_spring_rate(
        mean_coil_diameter=COIL,
        wire_diameter=WIRE,
        active_coils=ACTIVE_COILS,
        shear_modulus=SHEAR_MODULUS,
    )
    force = Quantity(
        magnitude=rate.to("N/mm").magnitude * WORKING_DEFLECTION.to("mm").magnitude,
        unit="N",
    )
    stress = spring_shear_stress(force=force, mean_coil_diameter=COIL, wire_diameter=WIRE)

    # The coil's own mass: wire cross-section x active wire length.
    wire_m = WIRE.to("m").magnitude
    coil_m = COIL.to("m").magnitude
    mass = WIRE_DENSITY * (pi * wire_m**2 / 4) * (pi * coil_m * ACTIVE_COILS)
    surge = spring_surge_frequency(
        spring_rate=rate, spring_mass=Quantity(magnitude=mass, unit="kg")
    )

    entries = [
        strength_scorecard(
            "return spring wire shear",
            stress=stress,
            allowable=SHEAR_ALLOWABLE,
            required=REQUIRED_SF,
        )
    ]
    for rpm in CAM_SPEEDS_RPM:
        floor = Quantity(magnitude=SURGE_MARGIN * rpm / 60.0, unit="Hz")
        entries.append(
            frequency_scorecard(
                f"coil surge at {rpm:.0f} rpm",
                frequency=surge,
                min_frequency=floor,
            )
        )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    card = screen_cam_return_spring()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
