"""Worked example: the same spreader beam, and the category decides whether it passes.

A 3 m spreader beam in A36, rated 5 tonnes, hung from two slings. The bending stress in
the beam and the tension across the net section of its end lugs are fixed by the geometry
and the load — nothing about them changes. What changes is ASME BTH-1's *design factor*,
and it is a design judgement, not a calculation:

* **Design Category A**, N_d = 2.00 — predictable loads, defined and controlled
  conditions, closely supervised use. Every allowable is S/2.
* **Design Category B**, N_d = 3.00 — anything less. Every allowable is S/3.

That is a 50% swing in every allowable stress, and it is invisible in the geometry. The
beam runs 107.6 MPa either way; the allowable is 124.0 MPa as Category A and 82.7 MPa as
Category B, so the same beam under the same load passes at SF 1.15 and **fails** at 0.77.
A margin quoted without its category cannot be checked, which is why this pack makes the
category a typed input rather than a bare safety factor a caller passes in.

The third row is the fatigue obligation, and it works the same way. BTH-1 Service Class
is set by the design life in load cycles, and Class 0 — up to 20,000 cycles — is the
only class that carries no fatigue analysis requirement at all. A beam expected to make
50,000 lifts is Class 1, needs a fatigue analysis, and gets NOT_EVALUATED here rather
than a pass, because no stress range was supplied. The 20,000-cycle boundary is the only
one in the table that changes whether a whole analysis is required, and "about twenty
thousand lifts" lands right on it.

Screening, not stamped design: BTH-1 also requires the lifter's welds, its connections,
its stability under an off-centre pick, its lifting-lug proof test and its marking. This
screens member stresses against BTH-1 allowables and reports the fatigue obligation. A
green scorecard does not make a lifter compliant.

Run it directly (``python examples/spreader_beam_bth1_category.py``);
:func:`screen_spreader_beam` is exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    DesignCategory,
    bth1_allowable_stresses,
    bth1_fatigue_scorecard,
    bth1_member_scorecard,
    service_class_for_cycles,
)
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

YIELD = Quantity.parse("248 MPa")  # A36, user-supplied
ULTIMATE = Quantity.parse("400 MPa")

# The beam: 3 m between sling points, rated 5 tonnes, W200x36 (S_x = 342,000 mm^3).
RATED_LOAD = Quantity.parse("49.05 kN")  # 5 tonnes
SPAN = Quantity.parse("3 m")
SECTION_MODULUS = Quantity.parse("342000 mm**3")

# The end lugs: 90 mm wide across a 30 mm pin hole, 20 mm plate, half the load each.
LUG_WIDTH = Quantity.parse("90 mm")
LUG_HOLE = Quantity.parse("30 mm")
LUG_THICKNESS = Quantity.parse("20 mm")

DESIGN_LIFE_CYCLES = 50_000


def beam_bending_stress() -> Quantity:
    """M/S for a centre-hung spreader: the rated load at midspan over two supports."""
    moment_n_mm = (
        RATED_LOAD.to("N").magnitude * SPAN.to("mm").magnitude / 4.0
    )  # P·L/4, simply supported
    return Quantity(magnitude=moment_n_mm / SECTION_MODULUS.to("mm**3").magnitude, unit="MPa")


def lug_net_tension_stress() -> Quantity:
    """P/2 across the lug's net section — the width less the hole, times the plate."""
    force = RATED_LOAD.to("N").magnitude / 2.0
    net_area = (LUG_WIDTH.to("mm").magnitude - LUG_HOLE.to("mm").magnitude) * LUG_THICKNESS.to(
        "mm"
    ).magnitude
    return Quantity(magnitude=force / net_area, unit="MPa")


def screen_spreader_beam(category: DesignCategory) -> Scorecard:
    """Screen the beam, the lugs and the fatigue obligation at one design category."""
    allowables = bth1_allowable_stresses(
        yield_strength=YIELD, ultimate_strength=ULTIMATE, category=category
    )
    service = service_class_for_cycles(DESIGN_LIFE_CYCLES)
    return Scorecard(
        entries=[
            bth1_member_scorecard(
                "beam bending",
                stress=beam_bending_stress(),
                allowable=allowables.bending,
                category=category,
            ),
            bth1_member_scorecard(
                "lug net tension",
                stress=lug_net_tension_stress(),
                allowable=allowables.tension_net,
                category=category,
            ),
            bth1_fatigue_scorecard(f"fatigue (Class {service.value})", service_class=service),
        ]
    )


def main() -> None:
    print(f"beam bending {beam_bending_stress().magnitude:.1f} MPa, ", end="")
    print(f"lug net tension {lug_net_tension_stress().magnitude:.1f} MPa")
    print(f"design life {DESIGN_LIFE_CYCLES:,} cycles -> ", end="")
    print(f"Service Class {service_class_for_cycles(DESIGN_LIFE_CYCLES).value}")
    for category in (DesignCategory.A, DesignCategory.B):
        card = screen_spreader_beam(category)
        nd = category.design_factor
        print(f"\n  Category {category.value} (N_d = {nd:.2f}) -> {card.status.value}")
        for entry in card.entries:
            factor = "  —  " if entry.safety_factor is None else f"{entry.safety_factor:.2f}"
            print(f"    {entry.name:<26} {entry.status.value:<14} SF {factor}")


if __name__ == "__main__":
    main()
