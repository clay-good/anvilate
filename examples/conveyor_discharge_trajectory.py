"""Worked example: where material lands off the end of a conveyor — the discharge trajectory.

Bulk material leaving the head pulley of a conveyor is a projectile: it flies off at the belt speed,
along the belt's angle, and falls under gravity until it meets the receiving chute or the next belt.
Placing that chute means predicting the throw — how far the stream carries and how long it is in the
air — and the drag-free projectile relations give a solid first cut for dense, fast material over
short distances involved. They ignore air drag and the spread of the stream, so they slightly
over-predict the reach of light or dusty material, but for sized ore or aggregate they are close.

This example takes material leaving a belt at 3 m/s, inclined 20° above horizontal at the head
pulley.
Treated as a projectile, it carries about 0.59 m horizontally before returning to launch height,
rises about 5.4 cm above the launch point, and is airborne for about 0.21 s. Those numbers place the
leading edge of the discharge stream and size the chute opening. The example reports the range, the
peak height, and the time of flight, so the discharge trajectory is explicit.

Run it directly (``python examples/conveyor_discharge_trajectory.py``);
:func:`discharge_trajectory` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    projectile_max_height,
    projectile_range,
    projectile_time_of_flight,
)
from anvilate.units import Quantity

BELT_SPEED = Quantity.parse("3 m/s")
DISCHARGE_ANGLE = 20.0  # head-pulley incline above horizontal


def discharge_trajectory() -> dict[str, float]:
    """Return the discharge range, peak height, and time of flight of the material stream."""
    reach = projectile_range(launch_speed=BELT_SPEED, launch_angle=DISCHARGE_ANGLE)
    height = projectile_max_height(launch_speed=BELT_SPEED, launch_angle=DISCHARGE_ANGLE)
    flight = projectile_time_of_flight(launch_speed=BELT_SPEED, launch_angle=DISCHARGE_ANGLE)
    return {
        "range_m": reach.to("m").magnitude,
        "peak_height_m": height.to("m").magnitude,
        "time_of_flight_s": flight.to("s").magnitude,
    }


def main() -> None:
    d = discharge_trajectory()
    print(f"horizontal throw: {d['range_m']:.2f} m")
    print(f"peak height above launch: {d['peak_height_m'] * 100:.1f} cm")
    print(f"time of flight: {d['time_of_flight_s']:.2f} s")


if __name__ == "__main__":
    main()
