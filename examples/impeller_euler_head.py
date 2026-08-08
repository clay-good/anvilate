"""Worked example: the Euler-head ceiling of a pump impeller, and its vane-angle penalty.

Euler's turbomachine equation sets the head an impeller can theoretically deliver from its geometry
and speed alone — the loss-free ceiling that the pump's actual, measured head always falls below.
The chain is three steps: the blade tip speed U = pi*D*N, the outlet swirl velocity that the vane
angle allows, and the Euler head that follows. The vane angle is the design lever: a backward-curved
vane sheds some head for a stable, non-overloading pump curve, which is why almost all process pumps
use one.

This example takes a 300 mm impeller at 1450 rpm with a 3 m/s meridional (through-flow) velocity.
The tip speed is about 22.8 m/s. With a backward-curved 25 deg vane the outlet swirl is about
16.3 m/s and the Euler head about 38.0 m. Swapping to a radial 90 deg vane recovers the full swirl
(c_theta = U) and lifts the Euler head to about 52.9 m — roughly 40% more head, but at the cost of
the stable characteristic. The example reports the tip speed and both heads so the trade is clear.

Run it directly (``python examples/impeller_euler_head.py``);
:func:`impeller_head` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    blade_tip_speed,
    euler_head,
    impeller_outlet_swirl_velocity,
)
from anvilate.units import Quantity

IMPELLER_DIAMETER = Quantity.parse("300 mm")
SPEED = Quantity.parse("1450 rpm")
MERIDIONAL_VELOCITY = Quantity.parse("3 m/s")
BACKWARD_VANE_DEG = 25.0
RADIAL_VANE_DEG = 90.0


def impeller_head() -> dict[str, float]:
    """Return the tip speed and the Euler head for a backward-curved and a radial vane."""
    tip_speed = blade_tip_speed(diameter=IMPELLER_DIAMETER, rotational_speed=SPEED)
    backward_swirl = impeller_outlet_swirl_velocity(
        blade_speed=tip_speed,
        meridional_velocity=MERIDIONAL_VELOCITY,
        blade_angle=BACKWARD_VANE_DEG,
    )
    radial_swirl = impeller_outlet_swirl_velocity(
        blade_speed=tip_speed,
        meridional_velocity=MERIDIONAL_VELOCITY,
        blade_angle=RADIAL_VANE_DEG,
    )
    backward_head = euler_head(outlet_blade_speed=tip_speed, outlet_swirl_velocity=backward_swirl)
    radial_head = euler_head(outlet_blade_speed=tip_speed, outlet_swirl_velocity=radial_swirl)
    return {
        "tip_speed_m_s": tip_speed.to("m/s").magnitude,
        "backward_vane_head_m": backward_head.to("m").magnitude,
        "radial_vane_head_m": radial_head.to("m").magnitude,
    }


def main() -> None:
    d = impeller_head()
    print(f"tip speed: {d['tip_speed_m_s']:.1f} m/s")
    print(f"Euler head, 25 deg backward vane: {d['backward_vane_head_m']:.1f} m")
    print(f"Euler head, 90 deg radial vane:  {d['radial_vane_head_m']:.1f} m")


if __name__ == "__main__":
    main()
