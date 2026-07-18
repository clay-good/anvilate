"""Capstone: the rotating shaft that is strong statically and lives on fatigue.

A 30 mm shaft carries a steady 200 N·m bending moment -- a pulley pulling sideways, say --
and it *rotates*. Check it the way a static part is checked and it looks robust: even with a
keyway doubling the local stress, the peak is 151 MPa against a 500 MPa yield, a safety factor
of 3.3. On a stationary shaft that would be the end of it.

But the shaft turns, and every fibre goes from full tension to full compression and back once
per revolution -- millions of fully reversed cycles. That is a fatigue problem, and fatigue
does not care about yield; it cares about a much lower endurance limit, cut further by three
things at once. The raw endurance limit is half the ultimate, 350 MPa, but the Marin factors
for a machined surface (0.75), a 30 mm size (0.86), and 99 % reliability (0.81) drag the usable
limit down to 183 MPa. The keyway then multiplies the *alternating* stress by a fatigue notch
factor of 1.8. Against that, the Goodman safety factor is 1.35 -- still safe, but less than
half the static margin, and it is the number that actually governs the life of the shaft.

The lesson is that a rotating shaft is a fatigue problem, not a strength problem, and the two
answers are far apart. Yield is divided down by surface finish, size, reliability, and the
notch before the real allowable appears, and a static check that ignores all four flatters the
design by a factor of two or more. Size a rotating shaft on its endurance limit, notched and
Marin-corrected, not on its yield.

Run it directly (``python examples/rotating_shaft_fatigue.py``);
:func:`screen_shaft` is also exercised in the test suite.
"""

from __future__ import annotations

from math import pi

from anvilate.analysis import (
    estimated_endurance_limit,
    fatigue_notch_factor,
    goodman_safety_factor,
    marin_endurance_limit,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

DIAMETER = Quantity.parse("30 mm")
BENDING_MOMENT = Quantity.parse("200 N*m")
ULTIMATE_STRENGTH = Quantity.parse("700 MPa")
YIELD_STRENGTH = Quantity.parse("500 MPa")
KEYWAY_KT = 2.0  # profiled keyway stress-concentration factor
NOTCH_SENSITIVITY = 0.8
SURFACE_FACTOR = 0.75  # machined
SIZE_FACTOR = 0.86  # ~30 mm
RELIABILITY_FACTOR = 0.81  # 99%
REQUIRED_STATIC_SAFETY = 1.5
REQUIRED_FATIGUE_SAFETY = 1.0


def _nominal_bending_stress() -> Quantity:
    """The round-shaft bending stress sigma = 32*M/(pi*d^3)."""
    m = BENDING_MOMENT.to("N*mm").magnitude
    d = DIAMETER.to("mm").magnitude
    return Quantity(magnitude=32.0 * m / (pi * d**3), unit="MPa")


def screen_shaft() -> Scorecard:
    """Screen the shaft on static yield (with the keyway) and on fatigue (Goodman)."""
    nominal = _nominal_bending_stress()
    # Static: the keyway raises the peak stress; check it against yield.
    static_peak = Quantity(magnitude=KEYWAY_KT * nominal.to("MPa").magnitude, unit="MPa")
    # Fatigue: a machined, sized, reliability-derated endurance limit, notched.
    endurance = marin_endurance_limit(
        base_endurance_limit=estimated_endurance_limit(ultimate_strength=ULTIMATE_STRENGTH),
        surface_factor=SURFACE_FACTOR,
        size_factor=SIZE_FACTOR,
        reliability_factor=RELIABILITY_FACTOR,
    )
    notch = fatigue_notch_factor(kt=KEYWAY_KT, notch_sensitivity=NOTCH_SENSITIVITY)
    # Rotation makes the bending fully reversed: all alternating, zero mean.
    alternating = Quantity(magnitude=notch * nominal.to("MPa").magnitude, unit="MPa")
    fatigue_sf = goodman_safety_factor(
        alternating_stress=alternating,
        mean_stress=Quantity.parse("0 MPa"),
        endurance_limit=endurance,
        ultimate_strength=ULTIMATE_STRENGTH,
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "static yield (keyway peak)",
                computed=YIELD_STRENGTH.to("MPa").magnitude / static_peak.to("MPa").magnitude,
                required=REQUIRED_STATIC_SAFETY,
            ),
            ScorecardEntry.from_safety_factor(
                "fatigue (Goodman, fully reversed)",
                computed=fatigue_sf,
                required=REQUIRED_FATIGUE_SAFETY,
            ),
        )
    )


def main() -> None:
    print(screen_shaft())


if __name__ == "__main__":
    main()
