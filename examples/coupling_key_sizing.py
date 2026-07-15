"""Worked example: the key that passed shear and brinelled the hub.

A coupling transmits 300 N·m through a 45 mm shaft on a 14 x 9 mm parallel key
(steel, 250 MPa yield). Sized the intuitive way — the tangential force F = 2T/d
= 13.3 kN shearing the key across its width — it needs only about 10 mm of
engagement, and a 10 mm key clears the shear screen at SF 1.5. But a parallel
key almost always fails in *bearing* first, not shear: the same force presses on
the key's side over only h/2 x L, so the side stress runs the higher of the two.
At 10 mm that bearing stress is 296 MPa — past yield — and the keyway sides
brinell into the hub. Screening the length each mode actually needs shows
bearing governs and calls for about 18 mm. Sizing a key on shear is sizing it on
the wrong failure mode.

Run it directly (``python examples/coupling_key_sizing.py``);
:func:`screen_coupling_key` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    key_bearing_stress,
    key_length_for_torque,
    key_shear_stress,
    strength_scorecard,
)
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

TORQUE = Quantity.parse("300 N*m")
SHAFT = Quantity.parse("45 mm")
KEY_WIDTH = Quantity.parse("14 mm")
KEY_HEIGHT = Quantity.parse("9 mm")
YIELD = Quantity.parse("250 MPa")  # key steel
SHEAR_YIELD = Quantity.parse("145 MPa")  # ~0.577*Sy (von Mises shear yield)
REQUIRED_SF = 1.5
# The key someone cut after sizing on shear alone (~10 mm meets shear at SF 1.5).
INSTALLED_LENGTH = Quantity.parse("10 mm")


def required_key_length():
    """The length each limit state needs at the design margin — bearing governs."""
    return key_length_for_torque(
        torque=TORQUE,
        shaft_diameter=SHAFT,
        key_width=KEY_WIDTH,
        key_height=KEY_HEIGHT,
        allowable_shear=Quantity(
            magnitude=SHEAR_YIELD.to("MPa").magnitude / REQUIRED_SF, unit="MPa"
        ),
        allowable_bearing=Quantity(magnitude=YIELD.to("MPa").magnitude / REQUIRED_SF, unit="MPa"),
    )


def screen_coupling_key() -> Scorecard:
    """Screen the shear-sized 10 mm key in both modes: it clears shear but fails
    bearing, the mode that actually governs a parallel key."""
    shear = key_shear_stress(
        torque=TORQUE, shaft_diameter=SHAFT, key_width=KEY_WIDTH, key_length=INSTALLED_LENGTH
    )
    bearing = key_bearing_stress(
        torque=TORQUE, shaft_diameter=SHAFT, key_height=KEY_HEIGHT, key_length=INSTALLED_LENGTH
    )
    return Scorecard(
        entries=(
            strength_scorecard(
                "key shear at 10 mm", stress=shear, allowable=SHEAR_YIELD, required=REQUIRED_SF
            ),
            strength_scorecard(
                "key bearing at 10 mm", stress=bearing, allowable=YIELD, required=REQUIRED_SF
            ),
        )
    )


def main() -> None:
    card = screen_coupling_key()
    for entry in card.entries:
        print(entry)
    print(card)
    req = required_key_length()
    print(
        f"sizing: shear needs {req.shear_length.to('mm')}, "
        f"bearing needs {req.bearing_length.to('mm')} "
        f"({req.governing_mode} governs -> {req.required_length.to('mm')})"
    )


if __name__ == "__main__":
    main()
