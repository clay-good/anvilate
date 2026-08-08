"""Worked example: a car rounding a flat curve.

Going around a bend, a car accelerates toward the centre of the turn, and tire friction supplies
the inward force. The centripetal acceleration and force size that demand, and the friction limit
fixes the fastest the car can take the curve before it slides.

A 1,000 kg car cornering at 25 m/s on a 50 m-radius curve accelerates inward at 12.5 m/s^2 (about
1.3 g), needing 12,500 N of centripetal force from its tires. On dry pavement (friction coefficient
0.8) the fastest it can round that curve without sliding is about 19.8 m/s — slower than 25 m/s, so
at 25 m/s it would skid. This example reports the centripetal acceleration, the centripetal force,
and the maximum no-slip cornering speed.

Run it directly (``python examples/car_cornering.py``);
:func:`cornering_dynamics` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    centripetal_acceleration,
    centripetal_force,
    maximum_cornering_speed,
)
from anvilate.units import Quantity

CAR_MASS = Quantity(magnitude=1000.0, unit="kg")
SPEED = Quantity(magnitude=25.0, unit="m/s")
RADIUS = Quantity(magnitude=50.0, unit="m")
FRICTION = 0.8  # dry pavement


def cornering_dynamics() -> dict[str, float]:
    """Return the centripetal acceleration, the centripetal force, and the max cornering speed."""
    accel = centripetal_acceleration(velocity=SPEED, radius=RADIUS)
    force = centripetal_force(mass=CAR_MASS, velocity=SPEED, radius=RADIUS)
    v_max = maximum_cornering_speed(friction_coefficient=FRICTION, radius=RADIUS)
    return {
        "centripetal_acceleration_m_s2": accel.to("m/s**2").magnitude,
        "centripetal_force_n": force.to("N").magnitude,
        "max_cornering_speed_m_s": v_max.to("m/s").magnitude,
    }


def main() -> None:
    d = cornering_dynamics()
    print(f"centripetal acceleration: {d['centripetal_acceleration_m_s2']:.1f} m/s^2")
    print(f"centripetal force: {d['centripetal_force_n']:.0f} N")
    print(f"max no-slip cornering speed: {d['max_cornering_speed_m_s']:.1f} m/s")


if __name__ == "__main__":
    main()
