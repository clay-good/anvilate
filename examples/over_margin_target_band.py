"""Worked example: the band that says a passing part is the wrong size.

Every other screen here answers one question — is it strong enough? A safety factor of
6.67 against a required 2.00 answers it *yes*, and says nothing about the steel you paid
for to get there. `constraints.max_safety_factor` is the other half: the top of a target
band, above which a check is `OVER_MARGIN` — a pass, never blocking, flagged so an
over-engineered part is as visible as a failing one.

One padeye, 120 mm wide with a 40 mm pin hole, carrying 60 kN, held to a band of 2.00–4.00,
at three plate thicknesses:

- **20 mm** — `OVER_MARGIN`. Net tension runs 6.67, past the top of the band, and the card
  says so. Nothing failed; 40% of the plate is doing no work.
- **12 mm** — `PASS`, and the reason this example exists: net tension lands on **4.00** and
  pin bearing on **2.00**. Both limit states sit exactly on a bound, which is what "the
  right size" looks like when you state one.
- **8 mm** — `FAIL`. Pin bearing at 1.33, below the floor.

Read the middle one against the first. Without the band, 20 mm and 12 mm are both "pass"
and a reviewer has no way to tell that one of them is 8 mm of wasted plate.

**The governing check follows the band.** On the 20 mm card `governing()` names the
over-margin check — not the tightest passing one — because the four rungs of the ranking
are the card's own roll-up order: `fail`, then `not_evaluated`, then `over_margin`, then
`pass`. A card that says `OVER_MARGIN` and points at an ordinary passing check would send
the reviewer to the wrong member.

**An over-margin entry carries no repair hint**, and that is deliberate: a hint belongs on a
check that needs one, and this check passed. The band tells you the part is oversized; the
size to use comes from the inverse for the *floor*, or from the next stock plate down.

The same band is reachable from a document — `constraints.max_safety_factor` beside
`min_safety_factor` — so a spec can ask to be told it is over-engineered without any code
at all. Both routes are screened below and give the same verdict.

Run it directly (``python examples/over_margin_target_band.py``); the screens are exercised
in the test suite.
"""

from __future__ import annotations

import yaml

from anvilate.packs.structural import LiftingLug, screen_lifting_lug
from anvilate.scorecard import CheckStatus, Scorecard
from anvilate.screening import screen_spec
from anvilate.spec import parse_spec
from anvilate.units import Quantity

WIDTH = Quantity.parse("120 mm")
HOLE = Quantity.parse("40 mm")
LOAD = Quantity.parse("60 kN")

# The band. The floor is the requirement; the ceiling is the question this example is about.
REQUIRED = 2.0
TARGET = 4.0

THICKNESSES = ("20 mm", "12 mm", "8 mm")

# The same part as a document, so the spec route can be screened beside the pack route.
_DOCUMENT = """
anvilate_spec: "1.3.0"
name: padeye
description: A lifting lug on a spreader beam.
units: {value: SI, origin: user_stated}
material: {ref: ASTM-A36}
manufacturing: {process: sheet_metal}
acceptance: {tiers: [T1_analytical]}
element_type: lifting_lug
element_params:
  name: padeye
  material: ASTM-A36
  width: {magnitude: 120.0, unit: mm}
  hole_diameter: {magnitude: 40.0, unit: mm}
  thickness: {magnitude: THICKNESS, unit: mm}
  load: {magnitude: 60.0, unit: kN}
constraints:
  min_safety_factor: {value: 2.0, origin: user_stated}
  max_safety_factor: {value: 4.0, origin: user_stated}
"""


def _lug(thickness: str) -> LiftingLug:
    return LiftingLug(
        name="padeye",
        width=WIDTH,
        hole_diameter=HOLE,
        thickness=Quantity.parse(thickness),
        load=LOAD,
        material="ASTM-A36",
    )


def screen_at(thickness: str) -> Scorecard:
    """The lug at one thickness, held to the two-sided band."""
    return screen_lifting_lug(
        _lug(thickness), required_safety_factor=REQUIRED, target_safety_factor=TARGET
    )


def screen_the_oversized_plate() -> Scorecard:
    """20 mm: passes both limit states and is flagged over-engineered."""
    return screen_at("20 mm")


def screen_the_right_plate() -> Scorecard:
    """12 mm: both limit states land exactly on a bound of the band."""
    return screen_at("12 mm")


def screen_the_thin_plate() -> Scorecard:
    """8 mm: pin bearing falls below the floor."""
    return screen_at("8 mm")


def screen_the_document(thickness: str = "20 mm") -> Scorecard:
    """The same band asked for by a Design Spec rather than a pack argument."""
    millimetres = Quantity.parse(thickness).to("mm").magnitude
    document = _DOCUMENT.replace("THICKNESS", f"{millimetres}")
    return screen_spec(parse_spec(yaml.safe_load(document)))


def main() -> None:
    print(f"padeye 120 mm x 40 mm hole, 60 kN, target band {REQUIRED:.2f}-{TARGET:.2f}\n")
    for thickness in THICKNESSES:
        card = screen_at(thickness)
        governing = card.governing()
        print(f"  {thickness:>5}  card {card.status.value:12s} governing {governing.name}")
        for entry in card.entries:
            factor = "—" if entry.safety_factor is None else f"{entry.safety_factor:.2f}"
            print(f"         {entry.status.value:12s} {entry.name:22s} SF {factor}")
        over = card.over_margin()
        if over:
            print(f"         over margin: {', '.join(e.name for e in over)}")
        print()

    print("the same band from a document, not a pack argument:")
    for thickness in ("20 mm", "12 mm"):
        card = screen_the_document(thickness)
        print(f"  constraints.max_safety_factor at {thickness:>5} -> {card.status.value}")

    thin = screen_the_thin_plate()
    assert thin.status is CheckStatus.FAIL
    assert screen_the_right_plate().status is CheckStatus.PASS
    assert screen_the_oversized_plate().status is CheckStatus.OVER_MARGIN


if __name__ == "__main__":
    main()
