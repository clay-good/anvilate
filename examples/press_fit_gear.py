"""Capstone: the press-fit gear that slips before anything breaks.

A gear is pressed onto a 50 mm shaft with a 0.02 mm radial interference, its hub 90 mm
across the outside, 40 mm of it gripping the shaft. It has to carry 1400 N·m. Three things
are checked, from the fit, the hub, and the shaft:

1. **Grip** -- the torque the friction of the interference fit can transmit before the gear
   slips on the shaft.
2. **Hub** -- the tangential (hoop) stress the fit raises at the hub bore, against yield.
3. **Shaft** -- the torsional shear stress in the shaft, against its allowable.

The parts are strong. The hub bore sees only 105 MPa against a 350 MPa yield (safety factor
3.34), and the shaft twists at 57 MPa against a 140 MPa allowable (2.45). Nothing is close to
breaking. But the **fit slips**: the friction grip transmits just 1303 N·m against the 1400
required, a safety factor of 0.93. The gear spins on the shaft under load, and neither the
hub nor the shaft ever knows.

The lesson is that a press fit is limited by *traction*, not strength -- whether the friction
holds, not whether the metal yields -- and the two are set by completely different things.
Grip comes from contact pressure times area; the fix is more of either. Lengthening the
engagement from 40 mm to 60 mm raises the grip to 1955 N·m (safety factor 1.40) without
touching the interference or the part sizes. A press-fit joint is sized by how hard and how
far it grips, and the strong shaft under it is beside the point.

Run it directly (``python examples/press_fit_gear.py``);
:func:`screen_press_fit` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    interference_fit,
    interference_torque_capacity,
    shaft_torsional_stress,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

RADIAL_INTERFERENCE = Quantity.parse("0.02 mm")
INTERFACE_DIAMETER = Quantity.parse("50 mm")
HUB_OUTER_DIAMETER = Quantity.parse("90 mm")
ELASTIC_MODULUS = Quantity.parse("200 GPa")
POISSON = 0.3
FRICTION = 0.15
REQUIRED_TORQUE = Quantity.parse("1400 N*m")
HUB_YIELD = Quantity.parse("350 MPa")
SHAFT_ALLOWABLE_SHEAR = Quantity.parse("140 MPa")

AS_DRAWN_ENGAGEMENT = Quantity.parse("40 mm")
LONGER_ENGAGEMENT = Quantity.parse("60 mm")


def _screen(engagement_length: Quantity) -> Scorecard:
    fit = interference_fit(
        radial_interference=RADIAL_INTERFERENCE,
        interface_diameter=INTERFACE_DIAMETER,
        hub_outer_diameter=HUB_OUTER_DIAMETER,
        hub_modulus=ELASTIC_MODULUS,
        hub_poisson=POISSON,
        shaft_modulus=ELASTIC_MODULUS,
        shaft_poisson=POISSON,
    )
    grip = interference_torque_capacity(
        contact_pressure=fit.contact_pressure,
        interface_diameter=INTERFACE_DIAMETER,
        engagement_length=engagement_length,
        friction_coefficient=FRICTION,
    )
    shaft_shear = shaft_torsional_stress(torque=REQUIRED_TORQUE, diameter=INTERFACE_DIAMETER)
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "fit grip (slip) vs required torque",
                computed=grip.to("N*m").magnitude / REQUIRED_TORQUE.to("N*m").magnitude,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "hub bore hoop stress",
                computed=HUB_YIELD.to("MPa").magnitude / fit.hub_hoop_stress.to("MPa").magnitude,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "shaft torsional shear",
                computed=SHAFT_ALLOWABLE_SHEAR.to("MPa").magnitude
                / shaft_shear.to("MPa").magnitude,
                required=1.0,
            ),
        )
    )


def screen_press_fit() -> Scorecard:
    """Screen the 40 mm-engagement fit: hub and shaft are strong, but the fit slips."""
    return _screen(AS_DRAWN_ENGAGEMENT)


def screen_longer_engagement() -> Scorecard:
    """Screen a 60 mm engagement: more grip area carries the torque without slipping."""
    return _screen(LONGER_ENGAGEMENT)


def main() -> None:
    print("as drawn (40 mm engagement):")
    print(screen_press_fit())
    print("\nlonger engagement (60 mm):")
    print(screen_longer_engagement())


if __name__ == "__main__":
    main()
