"""Worked example: the link that was strong once and broken a million times.

A steel tension link (700 MPa ultimate, 420 MPa yield, 200 mm² section) carries a
load that swings from 5 kN to 35 kN, over and over, at a drilled pin hole. Checked
the way a link is usually checked — peak load against yield — it is comfortable:
the 175 MPa peak stress sits at a 2.40 margin on yield. Statically, it is fine.

It does not fail statically. It fails by fatigue, and the check that catches it
composes four things a yield screen never touches. The cycle resolves into a
75 MPa alternating stress on a 100 MPa mean. The pin hole is a stress raiser
(K_t = 3.0), and with the steel's notch sensitivity the fatigue notch factor is
K_f = 2.8, which drives the *alternating* stress the crack actually feels to
210 MPa. The material's endurance limit, started from 0.5·S_u and discounted by
Marin factors for a machined, axial, mid-size part, is only 200 MPa. Put those on
the modified-Goodman line and the fatigue safety factor is 0.84 — below one. The
link that never yields will still crack, at the hole, after enough cycles.

Static strength and fatigue life are different questions, and a part sized on the
first can fail the second — especially at a stress raiser, where the alternating
stress is what counts. The fix is a gentler hole (a larger, chamfered bore drops
K_t) or a bigger section, not a stronger steel at the same notch. The strengths
and factors are material and geometry data, declared inline like any allowable.

Run it directly (``python examples/fatigue_link_stress_riser.py``);
:func:`screen_fatigue_link` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    cyclic_stress_components,
    estimated_endurance_limit,
    fatigue_notch_factor,
    goodman_safety_factor,
    marin_endurance_limit,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

SECTION_AREA = Quantity.parse("200 mm**2")
MAX_LOAD = Quantity.parse("35 kN")
MIN_LOAD = Quantity.parse("5 kN")
ULTIMATE_STRENGTH = Quantity.parse("700 MPa")
YIELD_STRENGTH = Quantity.parse("420 MPa")
STRESS_CONCENTRATION = 3.0  # K_t at the pin hole
NOTCH_SENSITIVITY = 0.9
SURFACE_FACTOR = 0.79  # machined
SIZE_FACTOR = 0.85
LOAD_FACTOR = 0.85  # axial


def _nominal_stress(load: Quantity) -> Quantity:
    magnitude = load.to("N").magnitude / SECTION_AREA.to("mm**2").magnitude
    return Quantity(magnitude=magnitude, unit="MPa")


def screen_fatigue_link() -> Scorecard:
    """Screen the link for static yield on the peak load AND modified-Goodman
    fatigue on the fluctuating cycle at the stress-raising hole."""
    peak = _nominal_stress(MAX_LOAD)
    cycle = cyclic_stress_components(
        max_stress=_nominal_stress(MAX_LOAD), min_stress=_nominal_stress(MIN_LOAD)
    )
    notch = fatigue_notch_factor(kt=STRESS_CONCENTRATION, notch_sensitivity=NOTCH_SENSITIVITY)
    endurance = marin_endurance_limit(
        base_endurance_limit=estimated_endurance_limit(ultimate_strength=ULTIMATE_STRENGTH),
        surface_factor=SURFACE_FACTOR,
        size_factor=SIZE_FACTOR,
        load_factor=LOAD_FACTOR,
    )
    fatigue_sf = goodman_safety_factor(
        alternating_stress=Quantity(
            magnitude=notch * cycle.alternating_stress.to("MPa").magnitude, unit="MPa"
        ),
        mean_stress=cycle.mean_stress,
        endurance_limit=endurance,
        ultimate_strength=ULTIMATE_STRENGTH,
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "static yield on peak load",
                computed=YIELD_STRENGTH.to("MPa").magnitude / peak.to("MPa").magnitude,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "modified-Goodman fatigue at the hole",
                computed=fatigue_sf,
                required=1.0,
            ),
        )
    )


def main() -> None:
    print(screen_fatigue_link())


if __name__ == "__main__":
    main()
