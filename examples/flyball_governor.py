"""Worked example: a flyball governor regulating an engine's speed.

A centrifugal governor holds an engine at a set speed by balancing the outward fling of its spinning
balls against gravity. The equilibrium ball height fixes a definite speed, so reading the height
tells you the speed — and adding a central load stiffens the response.

A Watt governor turning at 10 rad/s (about 95 rpm) settles with its balls about 98 mm below the
pivot; the height falls with the square of speed, so at higher speeds the governor grows less
sensitive. Reading a 98 mm height back gives the 10 rad/s speed. Fitting a Porter governor with a
5 kg central load on 1 kg balls raises the equilibrium height six-fold to about 588 mm at the same
speed, making it stiffer and usable at higher speeds. This example reports the Watt height, the
speed a height implies, and the Porter height with a central load.

Run it directly (``python examples/flyball_governor.py``);
:func:`governor_operating_point` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    porter_governor_height,
    watt_governor_height,
    watt_governor_speed,
)
from anvilate.units import Quantity

ANGULAR_SPEED = Quantity(magnitude=10.0, unit="rad/s")
BALL_MASS = Quantity(magnitude=1.0, unit="kg")
CENTRAL_LOAD = Quantity(magnitude=5.0, unit="kg")


def governor_operating_point() -> dict[str, float]:
    """Return the Watt height, the speed from that height, and the Porter height."""
    watt_h = watt_governor_height(angular_speed=ANGULAR_SPEED)
    speed = watt_governor_speed(height=watt_h)
    porter_h = porter_governor_height(
        angular_speed=ANGULAR_SPEED, ball_mass=BALL_MASS, central_load=CENTRAL_LOAD
    )
    return {
        "watt_height_mm": watt_h.to("m").magnitude * 1000.0,
        "speed_from_height_rad_s": speed.to("rad/s").magnitude,
        "porter_height_mm": porter_h.to("m").magnitude * 1000.0,
    }


def main() -> None:
    d = governor_operating_point()
    print(f"Watt governor height: {d['watt_height_mm']:.1f} mm")
    print(f"speed from that height: {d['speed_from_height_rad_s']:.2f} rad/s")
    print(f"Porter height with 5 kg load: {d['porter_height_mm']:.0f} mm")


if __name__ == "__main__":
    main()
