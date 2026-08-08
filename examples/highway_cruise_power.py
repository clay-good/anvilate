"""Worked example: the power a car needs to cruise, and why hills and speed hurt so much.

The power a vehicle draws at steady speed is set by its road load — rolling resistance, grade
resistance, and aerodynamic drag — times the speed. On the flat at moderate speed rolling resistance
leads, but aerodynamic drag climbs with the cube of speed in the power balance, so it takes over on
the highway; and a grade adds a big constant force that makes hill-climb the peak duty. Summing the
three forces and multiplying by speed gives the motor or engine rating a cruise needs, and over a
drive cycle it is the fuel or battery energy the vehicle spends.

This example cruises a 1500 kg car (rolling coefficient 0.012, drag coefficient 0.30, frontal area
2.2 m², air 1.225 kg/m³) at 100 km/h on the flat. Rolling resistance is about 177 N and aero drag
about 312 N, so the tractive force is roughly 489 N and the power about 13.6 kW — a modest cruise
load. Put the same car on a 5% grade (about 2.86°) and grade resistance adds roughly 735 N, more
than doubling the force to about 1224 N and the power to about 34 kW. The example reports the flat
power and the 5%-grade power, so why hills dominate a drivetrain's rating is explicit.

Run it directly (``python examples/highway_cruise_power.py``);
:func:`cruise_power` is also exercised in the test suite.
"""

from __future__ import annotations

from math import atan, degrees

from anvilate.analysis import (
    drag_force,
    grade_resistance_force,
    rolling_resistance_force,
    tractive_power,
)
from anvilate.units import Quantity

VEHICLE_MASS = Quantity.parse("1500 kg")
ROLLING_COEFFICIENT = 0.012
DRAG_COEFFICIENT = 0.30
FRONTAL_AREA = Quantity.parse("2.2 m**2")
AIR_DENSITY = Quantity.parse("1.225 kg/m**3")
CRUISE_SPEED = Quantity.parse("100 km/hr")
GRADE_ANGLE = degrees(atan(0.05))  # a 5% grade


def cruise_power() -> dict[str, float]:
    """Return the tractive power to cruise on the flat and on a 5% grade."""
    rolling = rolling_resistance_force(
        vehicle_mass=VEHICLE_MASS, rolling_resistance_coefficient=ROLLING_COEFFICIENT
    )
    aero = drag_force(
        density=AIR_DENSITY,
        velocity=CRUISE_SPEED,
        drag_coefficient=DRAG_COEFFICIENT,
        reference_area=FRONTAL_AREA,
    )
    grade = grade_resistance_force(vehicle_mass=VEHICLE_MASS, grade_angle=GRADE_ANGLE)
    flat_force = Quantity(magnitude=rolling.to("N").magnitude + aero.to("N").magnitude, unit="N")
    grade_total = flat_force.to("N").magnitude + grade.to("N").magnitude
    grade_force = Quantity(magnitude=grade_total, unit="N")
    flat_power = tractive_power(tractive_force=flat_force, speed=CRUISE_SPEED)
    grade_power = tractive_power(tractive_force=grade_force, speed=CRUISE_SPEED)
    return {
        "rolling_force_n": rolling.to("N").magnitude,
        "aero_force_n": aero.to("N").magnitude,
        "flat_power_kw": flat_power.to("kW").magnitude,
        "grade_power_kw": grade_power.to("kW").magnitude,
    }


def main() -> None:
    d = cruise_power()
    print(f"rolling resistance: {d['rolling_force_n']:.0f} N, aero drag: {d['aero_force_n']:.0f} N")
    print(f"power to cruise 100 km/h on the flat: {d['flat_power_kw']:.1f} kW")
    print(f"power on a 5% grade: {d['grade_power_kw']:.0f} kW (hills set the peak duty)")


if __name__ == "__main__":
    main()
