"""Worked example: the parking brake that only held one way.

A rail cart's drum brake presses a short lined shoe onto a 400 mm drum with a
hand lever: 200 N of operator force at 600 mm, the shoe normal force at
120 mm, the friction drag line 50 mm from the pivot, mu = 0.35. Holding the
loaded cart on the yard's grade takes 70 N*m.

Test it with the cart facing downhill and it passes: the drum turns so the
friction drag pulls the shoe *into* the drum (self-energizing), the lever's
force multiplies by c/(b - mu*a), and the brake holds 82 N*m. Roll the cart the
other way and the same drag now fights the lever -- c/(b + mu*a) -- and the
grip falls a third to 61 N*m: the cart creeps. Same brake, same hand force,
pass one way and fail the other. A drum brake has a rotation direction, and it
must be checked in the one that de-energizes the shoe. Here the honest fix is
leverage: an 800 mm handle holds 81 N*m even in the weak direction.

(The seductive fix -- shrinking b toward mu*a to exploit self-energizing --
runs toward the b <= mu*a self-locking limit, where the shoe grabs
uncontrollably; short_shoe_is_self_locking screens for it.)

The lining friction is manufacturer's data, declared inline like any allowable.

Run it directly (``python examples/cart_drum_brake.py``);
:func:`screen_cart_brake` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    short_shoe_brake_torque,
    short_shoe_is_self_locking,
    short_shoe_normal_force,
)
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

REQUIRED_TORQUE = Quantity.parse("70 N*m")
DRUM_DIAMETER = Quantity.parse("400 mm")
HAND_FORCE = Quantity.parse("200 N")
NORMAL_ARM = Quantity.parse("120 mm")  # pivot to shoe normal (b)
FRICTION_ARM = Quantity.parse("50 mm")  # pivot to friction drag line (a)
FRICTION = 0.35

LEVER_ARMS = {
    "600 mm lever": Quantity.parse("600 mm"),
    "800 mm lever": Quantity.parse("800 mm"),
}


def hold_torque(force_arm: Quantity, *, self_energizing: bool) -> Quantity:
    """The torque the shoe holds for a given lever length and drum direction."""
    normal = short_shoe_normal_force(
        actuation_force=HAND_FORCE,
        force_arm=force_arm,
        normal_arm=NORMAL_ARM,
        friction_arm=FRICTION_ARM,
        friction_coefficient=FRICTION,
        self_energizing=self_energizing,
    )
    return short_shoe_brake_torque(
        normal_force=normal, drum_diameter=DRUM_DIAMETER, friction_coefficient=FRICTION
    )


def screen_cart_brake() -> Scorecard:
    """Screen the as-built 600 mm lever in both drum directions, then the
    800 mm lever in the weak (de-energizing) direction."""
    required = REQUIRED_TORQUE.to("N*m").magnitude
    entries = [
        ScorecardEntry.from_safety_factor(
            "hold, drum forward (self-energizing)",
            computed=hold_torque(LEVER_ARMS["600 mm lever"], self_energizing=True)
            .to("N*m")
            .magnitude
            / required,
            required=1.0,
        ),
        ScorecardEntry.from_safety_factor(
            "hold, drum reverse (de-energizing)",
            computed=hold_torque(LEVER_ARMS["600 mm lever"], self_energizing=False)
            .to("N*m")
            .magnitude
            / required,
            required=1.0,
        ),
        ScorecardEntry.from_safety_factor(
            "800 mm lever, drum reverse",
            computed=hold_torque(LEVER_ARMS["800 mm lever"], self_energizing=False)
            .to("N*m")
            .magnitude
            / required,
            required=1.0,
        ),
    ]
    return Scorecard(entries=tuple(entries))


def main() -> None:
    locking = short_shoe_is_self_locking(
        normal_arm=NORMAL_ARM, friction_arm=FRICTION_ARM, friction_coefficient=FRICTION
    )
    print(f"self-locking geometry: {locking}")
    print(screen_cart_brake())


if __name__ == "__main__":
    main()
