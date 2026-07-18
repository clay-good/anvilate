"""Worked example: the cover bolts that carried more than the gauge suggested.

A 300 mm bore pressure vessel is closed by a bolted cover and runs at 16 bar. The
force trying to blow the cover off is the pressure acting over the *whole* bore
area, F = p*pi*D^2/4 = 113 kN — a lot more than the "16 bar isn't much" intuition
suggests, because pressure times a 300 mm circle is a big number. That force is
shared among the flange bolts, and each one carries it in tension through its
threads.

How many bolts it takes is a threads question. On four M12 class-8.8 bolts each
takes 28 kN, working the ISO 898 tensile stress area to 336 MPa — a 1.73 margin on
the 580 MPa proof strength, under the 2.0 a pressure joint wants. Six bolts drop
each share to 19 kN and clear it (2.59); eight give real margin (3.46). The bolts
must also be preloaded enough to seat the gasket, but even before that, the
pressure end-force alone sets a floor on the bolt count.

The load on a cover bolt is not the gauge pressure, it is that pressure times the
bore area divided by the bolt count — and the first number is bigger than it looks.
Count the bolts for the end-force, then preload them for the seal. The proof
strength is fastener-grade data, declared inline like any allowable.

Run it directly (``python examples/bolted_cover_flange.py``);
:func:`screen_cover_bolts` is also exercised in the test suite.
"""

from __future__ import annotations

from math import pi

from anvilate.analysis import bolt_axial_stress
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

INTERNAL_PRESSURE = Quantity.parse("1.6 MPa")  # 16 bar
BORE_DIAMETER = Quantity.parse("300 mm")
BOLT_DIAMETER = Quantity.parse("12 mm")
BOLT_PITCH = Quantity.parse("1.75 mm")
BOLT_PROOF_STRENGTH = Quantity.parse("580 MPa")  # class 8.8
MIN_SAFETY_FACTOR = 2.0

BOLT_COUNTS = {
    "4 bolts": 4,
    "6 bolts": 6,
    "8 bolts": 8,
}


def end_force() -> float:
    """The pressure end-force (N) trying to lift the cover: p * pi * D^2 / 4."""
    p = INTERNAL_PRESSURE.to("Pa").magnitude
    d = BORE_DIAMETER.to("m").magnitude
    return p * pi * d**2 / 4.0


def screen_cover_bolts() -> Scorecard:
    """Screen each bolt count: the per-bolt tensile stress must clear the 2.0
    proof-strength margin (safety factor = proof strength / bolt stress)."""
    proof = BOLT_PROOF_STRENGTH.to("MPa").magnitude
    force = end_force()
    entries = []
    for name, count in BOLT_COUNTS.items():
        stress = bolt_axial_stress(
            tension=Quantity(magnitude=force / count, unit="N"),
            nominal_diameter=BOLT_DIAMETER,
            pitch=BOLT_PITCH,
        )
        entries.append(
            ScorecardEntry.from_safety_factor(
                name,
                computed=proof / stress.to("MPa").magnitude,
                required=MIN_SAFETY_FACTOR,
            )
        )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    print(f"pressure end-force: {end_force() / 1000:.0f} kN")
    print(screen_cover_bolts())


if __name__ == "__main__":
    main()
