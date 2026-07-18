"""Worked example: the flange that holds the pressure and leaks anyway.

A 400 mm bolted flange runs at 2 MPa. The bolts are torqued to a total preload of 300 kN,
and a first check says that is plenty: the pressure trying to blow the flanges apart is the
hydrostatic end force H = (pi/4)*G^2*P = 251 kN, so 300 kN holds the joint shut with a
safety factor of 1.19. At assembly the same 300 kN also crushes the gasket home easily --
the seating load is only 138 kN (a factor of 2.17). The flange will not fly apart and the
gasket seats. It looks sealed.

It leaks, because keeping a joint tight takes more than out-pulling the pressure. Once the
vessel is up to pressure the bolts have to react the 251 kN end force *and still* keep a
residual crush on the gasket, or pressure creeps under the seal and it weeps. ASME sizes
the bolts for that combined operating load, H + 2*b*pi*G*m*P = 352 kN. The 300 kN preload
covers it only to 0.85: enough to hold the flanges together, not enough to keep the gasket
squeezed under pressure. The joint passes the two checks a designer reaches for first and
fails the one that actually governs.

The lesson is that a bolted flange has three bolt-load checks, not one: seat the gasket at
assembly, out-pull the end force, and -- the one that is quietly the largest here -- keep
enough gasket reaction under pressure to stay tight. The residual-crush term is set by the
gasket's m factor; a leak is fixed by more bolt preload (or a lower-m gasket), not by
thicker flanges. The end force alone never tells you whether a joint seals.

Run it directly (``python examples/gasket_flange_leak.py``);
:func:`screen_flange` is also exercised in the test suite.
"""

from __future__ import annotations

from math import pi

from anvilate.analysis import gasket
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

GASKET_MEAN_DIAMETER = Quantity.parse("400 mm")
EFFECTIVE_SEATING_WIDTH = Quantity.parse("10 mm")
SEATING_STRESS = Quantity.parse("11 MPa")  # ASME y, soft compressed gasket
GASKET_FACTOR = 2.0  # ASME m
PRESSURE = Quantity.parse("2 MPa")
TOTAL_BOLT_PRELOAD = Quantity.parse("300 kN")


def _hydrostatic_end_force() -> Quantity:
    g = GASKET_MEAN_DIAMETER.to("mm").magnitude
    p = PRESSURE.to("MPa").magnitude
    return Quantity(magnitude=pi / 4.0 * g**2 * p, unit="N")


def screen_flange() -> Scorecard:
    """Screen the bolt preload on seating, separation (end force), and operating tightness."""
    preload = TOTAL_BOLT_PRELOAD.to("kN").magnitude
    seating = gasket.gasket_seating_load(
        gasket_mean_diameter=GASKET_MEAN_DIAMETER,
        effective_seating_width=EFFECTIVE_SEATING_WIDTH,
        seating_stress=SEATING_STRESS,
    )
    operating = gasket.gasket_operating_load(
        gasket_mean_diameter=GASKET_MEAN_DIAMETER,
        effective_seating_width=EFFECTIVE_SEATING_WIDTH,
        gasket_factor=GASKET_FACTOR,
        pressure=PRESSURE,
    )
    end_force = _hydrostatic_end_force()
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "seat the gasket at assembly",
                computed=preload / seating.to("kN").magnitude,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "hold against the end force",
                computed=preload / end_force.to("kN").magnitude,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "stay tight under pressure",
                computed=preload / operating.to("kN").magnitude,
                required=1.0,
            ),
        )
    )


def main() -> None:
    print(screen_flange())


if __name__ == "__main__":
    main()
