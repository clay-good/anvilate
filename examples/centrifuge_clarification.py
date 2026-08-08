"""Worked example: sizing a lab centrifuge spin to clear fine particles from a suspension.

A centrifuge clears particles far faster than gravity by replacing g with the centrifugal field
omega^2*r, which at a few thousand rpm is thousands of times stronger. Two questions size a spin:
how fast does a particle sediment, and how long until it reaches the wall. Because the field grows
with radius, the travel time is not distance/velocity but an integral over radius, giving a log
term — the relation a tubular or decanter centrifuge is designed around.

This example clarifies a suspension of 1 micron, 1050 kg/m^3 particles in water (1000 kg/m^3,
1 mPa*s) in a rotor filling from a 50 mm inner radius to a 100 mm wall, spun at 10,000 rpm. At the
100 mm wall the sedimentation velocity is about 0.30 mm/s, and a particle starting at the surface
reaches the wall in about 228 s — under four minutes, versus the hours the same particle would take
under gravity alone. The example reports the wall sedimentation velocity and the settling time.

Run it directly (``python examples/centrifuge_clarification.py``);
:func:`clarify_suspension` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    centrifugal_sedimentation_velocity,
    centrifuge_settling_time,
)
from anvilate.units import Quantity

PARTICLE_DIAMETER = Quantity.parse("1 um")
DENSITY_PARTICLE = Quantity.parse("1050 kg/m**3")
DENSITY_FLUID = Quantity.parse("1000 kg/m**3")
VISCOSITY = Quantity.parse("0.001 Pa*s")
INNER_RADIUS = Quantity.parse("50 mm")
OUTER_RADIUS = Quantity.parse("100 mm")
SPEED = Quantity.parse("10000 rpm")


def clarify_suspension() -> dict[str, float]:
    """Return the wall sedimentation velocity and the surface-to-wall settling time."""
    velocity = centrifugal_sedimentation_velocity(
        particle_diameter=PARTICLE_DIAMETER,
        density_particle=DENSITY_PARTICLE,
        density_fluid=DENSITY_FLUID,
        viscosity=VISCOSITY,
        radius=OUTER_RADIUS,
        rotational_speed=SPEED,
    )
    time = centrifuge_settling_time(
        particle_diameter=PARTICLE_DIAMETER,
        density_particle=DENSITY_PARTICLE,
        density_fluid=DENSITY_FLUID,
        viscosity=VISCOSITY,
        inner_radius=INNER_RADIUS,
        outer_radius=OUTER_RADIUS,
        rotational_speed=SPEED,
    )
    return {
        "wall_velocity_mm_s": velocity.to("mm/s").magnitude,
        "settling_time_s": time.to("s").magnitude,
    }


def main() -> None:
    d = clarify_suspension()
    print(f"wall sedimentation velocity: {d['wall_velocity_mm_s']:.2f} mm/s")
    print(f"surface-to-wall settling time: {d['settling_time_s']:.0f} s")


if __name__ == "__main__":
    main()
