"""Worked example: the two web limit states at a beam's end bearing, lesser governs.

A concentrated reaction delivered into a beam's flange has to pass through the
thin web, and AISC 360-16 checks that web two ways at the same point: §J10.2 web
local *yielding* (the web crushing over the load's 2.5:1 spread) and §J10.3 web
local *crippling* (the same web buckling out of plane). Both are always checked
and the smaller strength governs — a hand check that stops at yielding can miss
that crippling is the real limit.

Here a shallow W-shape (6 mm web, 9 mm flange, 350 mm deep, A992) sits on a 90 mm
bearing at its end. Yielding gives 315.7 kN but crippling only 212.6 kN, so the
thin web buckles before it crushes and crippling sets the ~213 kN bearing capacity.

Run it directly (``python examples/beam_bearing_web_checks.py``);
:func:`end_bearing_capacity` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    aisc_web_crippling_strength,
    aisc_web_local_yielding_strength,
)
from anvilate.units import Quantity

WEB_THICKNESS = Quantity.parse("6 mm")
FLANGE_THICKNESS = Quantity.parse("9 mm")
MEMBER_DEPTH = Quantity.parse("350 mm")
FILLET_DISTANCE = Quantity.parse("25 mm")
BEARING_LENGTH = Quantity.parse("90 mm")
WEB_YIELD = Quantity.parse("345 MPa")
ELASTIC_MODULUS = Quantity.parse("200000 MPa")


def end_bearing_capacity() -> dict[str, Quantity]:
    """Return the two §J10 web strengths and the governing (lesser) one."""
    yielding = aisc_web_local_yielding_strength(
        web_yield=WEB_YIELD,
        web_thickness=WEB_THICKNESS,
        fillet_distance=FILLET_DISTANCE,
        bearing_length=BEARING_LENGTH,
        at_member_end=True,
    )
    crippling = aisc_web_crippling_strength(
        web_thickness=WEB_THICKNESS,
        flange_thickness=FLANGE_THICKNESS,
        member_depth=MEMBER_DEPTH,
        bearing_length=BEARING_LENGTH,
        web_yield=WEB_YIELD,
        elastic_modulus=ELASTIC_MODULUS,
        at_member_end=True,
    )
    governing = min(yielding, crippling, key=lambda q: q.to("kN").magnitude)
    return {"yielding": yielding, "crippling": crippling, "governing": governing}


def main() -> None:
    result = end_bearing_capacity()
    for name in ("yielding", "crippling"):
        print(f"web local {name}: {result[name].to('kN').magnitude:.1f} kN")
    gov = result["governing"].to("kN").magnitude
    which = "crippling" if result["governing"] is result["crippling"] else "yielding"
    print(f"governing (web local {which}): {gov:.1f} kN")


if __name__ == "__main__":
    main()
