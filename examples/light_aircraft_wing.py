"""Worked example: the wing of a small general-aviation aircraft.

A wing has to make enough lift to hold the aircraft up, and the price of that lift is the induced
drag from the trailing vortices its finite span sheds. The stall speed then fixes how slow the
aircraft can fly before the wing can no longer carry its weight. These three numbers size a wing.

Take a light aircraft with a 16 m^2 wing cruising at 50 m/s through sea-level air (1.225 kg/m^3) at
a lift coefficient of 0.5. The wing makes about 12,250 N of lift. With an aspect ratio of 7.5 and an
Oswald efficiency of 0.8, generating that lift costs an induced-drag coefficient of about 0.0133. At
its 12,000 N weight and a maximum lift coefficient of 1.5, the stall speed is about 28.6 m/s — the
slowest it can fly. This example reports the lift force, the induced-drag coefficient, and the stall
speed.

Run it directly (``python examples/light_aircraft_wing.py``);
:func:`wing_performance` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    induced_drag_coefficient,
    lift_force,
    stall_speed,
)
from anvilate.units import Quantity

AIR_DENSITY = Quantity(magnitude=1.225, unit="kg/m**3")  # sea level
AIRSPEED = Quantity(magnitude=50.0, unit="m/s")
WING_AREA = Quantity(magnitude=16.0, unit="m**2")
LIFT_COEFFICIENT = 0.5
ASPECT_RATIO = 7.5
OSWALD_EFFICIENCY = 0.8
WEIGHT = Quantity(magnitude=12000.0, unit="N")
MAX_LIFT_COEFFICIENT = 1.5


def wing_performance() -> dict[str, float]:
    """Return the lift force, induced-drag coefficient, and stall speed."""
    lift = lift_force(
        air_density=AIR_DENSITY,
        airspeed=AIRSPEED,
        wing_area=WING_AREA,
        lift_coefficient=LIFT_COEFFICIENT,
    )
    cdi = induced_drag_coefficient(
        lift_coefficient=LIFT_COEFFICIENT,
        aspect_ratio=ASPECT_RATIO,
        oswald_efficiency=OSWALD_EFFICIENCY,
    )
    v_stall = stall_speed(
        weight=WEIGHT,
        air_density=AIR_DENSITY,
        wing_area=WING_AREA,
        max_lift_coefficient=MAX_LIFT_COEFFICIENT,
    )
    return {
        "lift_force_n": lift.to("N").magnitude,
        "induced_drag_coefficient": cdi,
        "stall_speed_m_s": v_stall.to("m/s").magnitude,
    }


def main() -> None:
    d = wing_performance()
    print(f"lift force: {d['lift_force_n']:.0f} N")
    print(f"induced-drag coefficient: {d['induced_drag_coefficient']:.4f}")
    print(f"stall speed: {d['stall_speed_m_s']:.1f} m/s")


if __name__ == "__main__":
    main()
