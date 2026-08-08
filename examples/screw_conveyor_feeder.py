"""Worked example: rating a screw feeder and setting its drive speed to a target tonnage.

A screw conveyor (auger) meters bulk material by rotating a helical flight in a trough: each turn
advances the load one pitch, so the throughput is the swept annulus times the pitch times the speed
times a fill fraction that stays well below one to keep the flight from flooding. Unlike a belt, the
rate is set by geometry and rpm, not by a belt speed — which is exactly what makes a screw a good
metering feeder.

This example takes a 250 mm screw on a 60 mm core at a standard 250 mm pitch, running a 750 kg/m³
meal at a conservative 0.3 trough loading. At 45 rpm it sweeps about 9.4 m³/h, which at this density
is about 7.0 t/h. To lift that to a 15 t/h target the drive must turn about 96 rpm — the inverse
solves the speed directly, so the operator can dial in tonnage rather than guess. The example
reports the rated volume and mass at 45 rpm and the speed the 15 t/h target needs.

Run it directly (``python examples/screw_conveyor_feeder.py``);
:func:`feeder_rating` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    screw_conveyor_mass_capacity,
    screw_conveyor_speed_for_capacity,
    screw_conveyor_volumetric_capacity,
)
from anvilate.units import Quantity

SCREW_DIAMETER = Quantity.parse("250 mm")
SHAFT_DIAMETER = Quantity.parse("60 mm")
PITCH = Quantity.parse("250 mm")
FILL_FRACTION = 0.3
BULK_DENSITY = Quantity.parse("750 kg/m**3")
RATED_SPEED = Quantity.parse("45 rpm")
TARGET_RATE = Quantity.parse("15 t/hr")


def feeder_rating() -> dict[str, float]:
    """Return the rated volume/mass at 45 rpm and the screw speed a 15 t/h target needs."""
    volume = screw_conveyor_volumetric_capacity(
        screw_diameter=SCREW_DIAMETER,
        shaft_diameter=SHAFT_DIAMETER,
        pitch=PITCH,
        rotational_speed=RATED_SPEED,
        fill_fraction=FILL_FRACTION,
    )
    mass = screw_conveyor_mass_capacity(volumetric_capacity=volume, bulk_density=BULK_DENSITY)
    target_volume = Quantity(
        magnitude=TARGET_RATE.to("kg/s").magnitude / BULK_DENSITY.to("kg/m**3").magnitude,
        unit="m**3/s",
    )
    speed = screw_conveyor_speed_for_capacity(
        volumetric_capacity=target_volume,
        screw_diameter=SCREW_DIAMETER,
        shaft_diameter=SHAFT_DIAMETER,
        pitch=PITCH,
        fill_fraction=FILL_FRACTION,
    )
    return {
        "rated_volume_m3_h": volume.to("m**3/h").magnitude,
        "rated_mass_t_h": mass.to("t/hr").magnitude,
        "speed_for_target_rpm": speed.to("rpm").magnitude,
    }


def main() -> None:
    d = feeder_rating()
    print(f"at 45 rpm: {d['rated_volume_m3_h']:.1f} m^3/h ({d['rated_mass_t_h']:.1f} t/h)")
    print(f"speed for a 15 t/h target: {d['speed_for_target_rpm']:.0f} rpm")


if __name__ == "__main__":
    main()
