"""Worked example: screening a coped beam web in direct shear with the structural pack.

Declares the web of a coped W410x46.1 beam (A992, 7.0 mm web) at a bolted end
connection — three M20 bolts in 22 mm holes through a 250 mm engaged depth —
carrying a 150 kN end reaction, and screens both AISC 360-16 §J4.2 shear limit
states in one call. The instructive part: on the gross section, shear yielding
(0.60·Fy·A_gv) has the larger margin, but the three bolt holes cut the net shear
area enough that shear rupture (0.60·Fu·A_nv) governs — a gross-area-only hand
check would overstate the connection's margin.

Run it directly (``python examples/coped_beam_web_shear.py``);
:func:`screen_coped_web` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.packs.structural import ShearPlate, screen_structure
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

END_REACTION = Quantity.parse("150 kN")

WEB_THICKNESS_MM = 7.0  # W410x46.1 web
ENGAGED_DEPTH_MM = 250.0  # web depth along the bolt line after the cope
HOLE_DIAMETER_MM = 22.0  # M20 bolts in standard holes
BOLT_COUNT = 3


def screen_coped_web() -> Scorecard:
    """Declare and screen the coped beam web, returning the scorecard."""
    gross = ENGAGED_DEPTH_MM * WEB_THICKNESS_MM
    net = gross - BOLT_COUNT * HOLE_DIAMETER_MM * WEB_THICKNESS_MM
    web = ShearPlate(
        name="coped web",
        gross_shear_area=Quantity.parse(f"{gross} mm**2"),
        net_shear_area=Quantity.parse(f"{net} mm**2"),
        load=END_REACTION,
        material="ASTM-A992",
    )
    # AISC ASD: Omega = 2.00 on shear rupture (the governing limit state here).
    return screen_structure([web], required_safety_factor=2.0)


def main() -> None:
    card = screen_coped_web()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
