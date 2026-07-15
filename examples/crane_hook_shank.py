"""Worked example: the crane hook the straight-beam formula passed.

A 20 kN (2-tonne) crane hook has a rectangular shank section: 25 mm wide,
50 mm deep, its bore 40 mm from the hook's centre of curvature. The load
hanging in the saddle bends the shank about its centroid with M = P*r_c and
stretches it with P/A on top. Screened with the familiar straight-beam
6M/(b*h^2) + P/A, the bore sees 141 MPa -- a 2.20 factor against the 310 MPa
yield, comfortably over the required 2.0. Ship it?

No. The shank is *curved*, r_c/h barely 1.3, and curvature crowds the stress
onto the bore: Winkler's hyperbolic distribution puts the inner fibre at
185 MPa -- 31% above the straight-beam number -- and the true factor is 1.68,
under the requirement. This is exactly where service cracks appear on hooks:
the inside of the curve, at a stress the linear formula never saw. Deepening
the shank to 60 mm calms the bore to 145 MPa (SF 2.14) and passes honestly.

The required factor of 2.0 and the 310 MPa yield are the engineer's inputs,
declared inline like any allowable.

Run it directly (``python examples/crane_hook_shank.py``);
:func:`screen_crane_hook` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import rectangular_curved_beam_stress
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

LOAD = Quantity.parse("20 kN")
WIDTH = Quantity.parse("25 mm")
INNER_RADIUS = Quantity.parse("40 mm")
YIELD_STRENGTH = Quantity.parse("310 MPa")
REQUIRED_SF = 2.0

DEPTHS = (Quantity.parse("50 mm"), Quantity.parse("60 mm"))


def _bore_stress_winkler(depth: Quantity) -> float:
    """The true bore stress in MPa: Winkler bending (M = P*r_c) plus direct P/A."""
    ri = INNER_RADIUS.to("mm").magnitude
    h = depth.to("mm").magnitude
    rc = ri + h / 2.0
    moment = Quantity(magnitude=LOAD.to("N").magnitude * rc, unit="N*mm")
    bending = rectangular_curved_beam_stress(
        moment=moment,
        inner_radius=INNER_RADIUS,
        outer_radius=Quantity(magnitude=ri + h, unit="mm"),
        width=WIDTH,
    )
    area = WIDTH.to("mm").magnitude * h
    direct = LOAD.to("N").magnitude / area
    return bending.inner_stress.to("MPa").magnitude + direct


def _bore_stress_straight(depth: Quantity) -> float:
    """What the straight-beam screen claims, 6M/(b*h^2) + P/A, in MPa."""
    ri = INNER_RADIUS.to("mm").magnitude
    h = depth.to("mm").magnitude
    b = WIDTH.to("mm").magnitude
    rc = ri + h / 2.0
    moment = LOAD.to("N").magnitude * rc
    return 6.0 * moment / (b * h * h) + LOAD.to("N").magnitude / (b * h)


def screen_crane_hook() -> Scorecard:
    """Screen the 50 mm shank bore with the straight-beam formula and with
    Winkler curved-beam theory, then the deepened 60 mm shank (Winkler)."""
    allow = YIELD_STRENGTH.to("MPa").magnitude
    entries = [
        ScorecardEntry.from_safety_factor(
            "bore, straight-beam screen (h=50)",
            computed=allow / _bore_stress_straight(DEPTHS[0]),
            required=REQUIRED_SF,
        ),
        ScorecardEntry.from_safety_factor(
            "bore, Winkler curved-beam (h=50)",
            computed=allow / _bore_stress_winkler(DEPTHS[0]),
            required=REQUIRED_SF,
        ),
        ScorecardEntry.from_safety_factor(
            "bore, Winkler curved-beam (h=60)",
            computed=allow / _bore_stress_winkler(DEPTHS[1]),
            required=REQUIRED_SF,
        ),
    ]
    return Scorecard(entries=tuple(entries))


def main() -> None:
    for depth in DEPTHS:
        h = depth.to("mm").magnitude
        print(
            f"h={h:.0f} mm: straight-beam bore {_bore_stress_straight(depth):.1f} MPa, "
            f"Winkler bore {_bore_stress_winkler(depth):.1f} MPa"
        )
    print(screen_crane_hook())


if __name__ == "__main__":
    main()
