"""Worked example: sizing a gear shaft — three subsystems, one coupled chain.

A real machine element is rarely one check. This gearbox intermediate shaft carries
15 kW at 1500 rpm through a spur gear at mid-span, and three different subsystems each
set part of the design, in sequence:

  1. The transmitted torque and the gear's tangential + radial load fix a steady torque
     and a *fully reversed* bending moment on the rotating shaft.
  2. Those loads size the shaft by the DE-Goodman fatigue criterion — here a 28.5 mm
     minimum, rounded up to a standard 30 mm.
  3. On that 30 mm shaft a standard 8x7 key transmits the torque over a required length,
     and the bearings carrying the gear reaction reach an L10 life.

No single check is the design; the shaft fatigue sets the diameter, and the key length
and bearing life follow from it. The example composes six verified functions across the
torsion, gear, bearing, and key modules and reports what each subsystem needs.

Run it directly (``python examples/gear_shaft_assembly.py``);
:func:`size_the_shaft_assembly` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    bearing_life_hours,
    gear_radial_load,
    gear_tangential_load,
    key_length_for_torque,
    shaft_diameter_de_goodman,
    torque_from_power,
)
from anvilate.units import Quantity

POWER = Quantity.parse("15 kW")
SPEED = Quantity.parse("1500 rpm")
GEAR_PITCH_DIAMETER = Quantity.parse("120 mm")
PRESSURE_ANGLE = 20.0
SPAN = Quantity.parse("300 mm")  # bearing to bearing, gear central
STANDARD_SHAFT = Quantity.parse("30 mm")  # 28.5 mm fatigue minimum rounded up
BEARING_RATING = Quantity.parse("20 kN")  # catalogue dynamic load rating C


def size_the_shaft_assembly() -> dict[str, float]:
    """Return the shaft fatigue diameter, the key length, and the bearing L10 life."""
    torque = torque_from_power(power=POWER, rotational_speed=SPEED)

    tangential = gear_tangential_load(torque=torque, pitch_diameter=GEAR_PITCH_DIAMETER)
    radial = gear_radial_load(tangential_load=tangential, pressure_angle=PRESSURE_ANGLE)
    gear_force = (tangential.to("N").magnitude ** 2 + radial.to("N").magnitude ** 2) ** 0.5

    span_mm = SPAN.to("mm").magnitude
    bending_amplitude = Quantity(magnitude=gear_force * span_mm / 4 / 1000, unit="N*m")
    reaction = Quantity(magnitude=gear_force / 2, unit="N")

    diameter = shaft_diameter_de_goodman(
        alternating_bending_moment=bending_amplitude,
        mean_torque=torque,
        endurance_limit=Quantity.parse("200 MPa"),
        ultimate_strength=Quantity.parse("600 MPa"),
        bending_fatigue_factor=1.5,
        torsion_fatigue_factor=1.3,
        required_safety_factor=2.0,
    )

    key = key_length_for_torque(
        torque=torque,
        shaft_diameter=STANDARD_SHAFT,
        key_width=Quantity.parse("8 mm"),
        key_height=Quantity.parse("7 mm"),
        allowable_shear=Quantity.parse("60 MPa"),
        allowable_bearing=Quantity.parse("120 MPa"),
    )

    life = bearing_life_hours(
        dynamic_load_rating=BEARING_RATING, equivalent_load=reaction, speed=SPEED
    )

    return {
        "shaft_diameter_mm": diameter.to("mm").magnitude,
        "key_length_mm": key.required_length.to("mm").magnitude,
        "bearing_life_hours": life.to("hour").magnitude,
    }


def main() -> None:
    result = size_the_shaft_assembly()
    print(f"shaft diameter (DE-Goodman fatigue): {result['shaft_diameter_mm']:.1f} mm")
    print(f"key length (8x7 on 30 mm shaft)    : {result['key_length_mm']:.1f} mm")
    print(f"bearing L10 life                   : {result['bearing_life_hours']:,.0f} hours")


if __name__ == "__main__":
    main()
