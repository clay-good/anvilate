"""Worked example: surface contact stress of a crane wheel on a rail.

A distinct failure mode from bulk stress: where a hard wheel rolls on a flat rail,
the load funnels through a contact strip millimetres wide and drives a local
pressure far above any nominal bearing stress — the mechanism behind spalling and
rolling-contact fatigue. This screen turns a Ø100 mm steel wheel carrying a 20 kN
load across a 40 mm tread into its Hertzian line-contact peak pressure and checks
it against the rail steel's yield.

The result is instructive: against *annealed* 4140 (a soft 417 MPa yield) the
~600 MPa contact pressure fails the screen outright — which is exactly why crane
wheels and rails are surface-hardened rather than run soft. The check is also
deliberately conservative: it screens the *surface* peak pressure against yield,
while true yield onset is governed by the subsurface shear stress (~0.30·p_max,
deeper in the material), so a part that clears it has more real margin than the
number suggests.

Run it directly (``python examples/wheel_rail_contact.py``); :func:`screen_wheel_contact`
is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import hertz_cylinder_contact, strength_scorecard
from anvilate.scorecard import Scorecard
from anvilate.standards import default_materials_db
from anvilate.units import Quantity

WHEEL_DIAMETER = Quantity.parse("100 mm")
TREAD_WIDTH = Quantity.parse("40 mm")
WHEEL_LOAD = Quantity.parse("20 kN")
STEEL = "AISI-4140"


def screen_wheel_contact() -> Scorecard:
    """Compute the wheel/rail contact pressure and screen it against yield."""
    steel = default_materials_db().get(STEEL)
    contact = hertz_cylinder_contact(
        force=WHEEL_LOAD,
        length=TREAD_WIDTH,
        diameter1=WHEEL_DIAMETER,  # the wheel
        modulus1=steel.elastic_modulus.quantity,
        poisson1=steel.poisson_ratio.value,
        modulus2=steel.elastic_modulus.quantity,
        poisson2=steel.poisson_ratio.value,
        # diameter2 omitted -> the flat rail (infinite radius)
    )
    entry = strength_scorecard(
        "wheel/rail surface contact",
        stress=contact.max_contact_pressure,
        allowable=steel.yield_strength.quantity,
        required=1.2,
    )
    return Scorecard(entries=(entry,))


def main() -> None:
    card = screen_wheel_contact()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
