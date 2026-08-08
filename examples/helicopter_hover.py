"""Worked example: the hover performance of a light helicopter rotor.

A hovering rotor accelerates air down through its disk, and actuator-disk momentum theory sets the
downwash it induces, the least power hover can possibly cost, and — against the real shaft power —
how efficient the rotor actually is.

Take a rotor carrying 5,000 N of thrust with a 2 m radius (a 12.6 m^2 disk) in sea-level air
(1.225 kg/m^3). The induced downwash is about 12.7 m/s, and the ideal hover power is about 63.7 kW —
the floor no rotor of this size and loading can beat. A real rotor that actually draws 85 kW to make
that thrust has a figure of merit of about 0.75, meaning three-quarters of its power goes to useful
induced work and the rest to profile drag and swirl. This example reports the induced velocity, the
ideal hover power, and the figure of merit.

Run it directly (``python examples/helicopter_hover.py``);
:func:`rotor_hover` is also exercised in the test suite.
"""

from __future__ import annotations

from math import pi

from anvilate.analysis import (
    figure_of_merit,
    hover_induced_velocity,
    ideal_hover_power,
)
from anvilate.units import Quantity

THRUST = Quantity(magnitude=5000.0, unit="N")
AIR_DENSITY = Quantity(magnitude=1.225, unit="kg/m**3")  # sea level
DISK_AREA = Quantity(magnitude=pi * 2.0**2, unit="m**2")  # 2 m radius
ACTUAL_POWER = Quantity(magnitude=85000.0, unit="W")


def rotor_hover() -> dict[str, float]:
    """Return the induced velocity, ideal hover power, and figure of merit."""
    v_h = hover_induced_velocity(thrust=THRUST, air_density=AIR_DENSITY, disk_area=DISK_AREA)
    power = ideal_hover_power(thrust=THRUST, air_density=AIR_DENSITY, disk_area=DISK_AREA)
    fm = figure_of_merit(
        thrust=THRUST,
        air_density=AIR_DENSITY,
        disk_area=DISK_AREA,
        actual_power=ACTUAL_POWER,
    )
    return {
        "induced_velocity_m_s": v_h.to("m/s").magnitude,
        "ideal_hover_power_kw": power.to("W").magnitude / 1000.0,
        "figure_of_merit": fm,
    }


def main() -> None:
    d = rotor_hover()
    print(f"induced downwash velocity: {d['induced_velocity_m_s']:.2f} m/s")
    print(f"ideal hover power: {d['ideal_hover_power_kw']:.1f} kW")
    print(f"figure of merit: {d['figure_of_merit']:.3f}")


if __name__ == "__main__":
    main()
