"""Worked example: sizing a column base plate (AISC concrete bearing + plate bending).

The bread-and-butter task the structural persona spends hours on in Excel: a steel
column delivers 800 kN to a 400 x 400 mm base plate on a concrete footing, and the
plate must (1) spread the load without over-stressing the concrete and (2) be thick
enough not to bend open under the upward bearing pressure. This screen runs both
AISC checks at once — concrete bearing P/(B·N) vs 0.85·f'c (§J8) and the
cantilever plate-bending stress 3·f_p·l²/t² vs the plate yield (Design Guide 1).

The instructive result: the 25 mm plate clears bearing comfortably but its bending
stress (~240 MPa) sits right at A36's 250 MPa yield, so at a 1.5 safety factor the
plate-bending check governs and FAILs — the plate needs to be thicker, exactly the
call an engineer makes by hand.

Run it directly (``python examples/column_base_plate.py``); :func:`screen_base_plate_design`
is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.packs.structural import BasePlate, screen_base_plate
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity


def screen_base_plate_design() -> Scorecard:
    """Declare and screen the column base plate, returning its scorecard."""
    plate = BasePlate(
        name="col_base",
        width=Quantity.parse("400 mm"),
        depth=Quantity.parse("400 mm"),
        axial_load=Quantity.parse("800 kN"),
        concrete_strength=Quantity.parse("25 MPa"),  # f'c
        plate_thickness=Quantity.parse("25 mm"),
        cantilever=Quantity.parse("100 mm"),  # overhang beyond the column footprint
        plate_material="ASTM-A36",
    )
    return screen_base_plate(plate, required_safety_factor=1.5)


def main() -> None:
    card = screen_base_plate_design()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
