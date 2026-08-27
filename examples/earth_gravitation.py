"""Worked example: Earth's gravity, from its mass to a low orbit.

Newton's law of gravitation ties a body's mass to everything around it: the force it exerts on
another mass, the gravity felt at its surface, and — through the standard gravitational parameter
μ = G·M — the speed of anything orbiting it. This example runs that chain for Earth.

Earth's mass of 5.972e24 kg gives a surface gravity of about 9.82 m/s^2 (the familiar g) and a
standard gravitational parameter of about 3.986e14 m^3/s^2. Feeding that μ into the circular-orbit
relation, a satellite skimming 400 km up (orbital radius ~6,771 km) must travel about 7,672 m/s. The
same law gives the pull between two 1,000 kg masses a metre apart — a mere 6.7e-5 N, showing how
feeble gravity is between everyday objects. This example reports the surface gravity, the
gravitational parameter, the low-orbit speed it implies, and that everyday pull.

Run it directly (``python examples/earth_gravitation.py``);
:func:`earth_gravity_chain` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    circular_orbit_velocity,
    gravitational_force,
    gravitational_parameter,
    surface_gravity,
)
from anvilate.units import Quantity

EARTH_MASS = Quantity(magnitude=5.972e24, unit="kg")
EARTH_RADIUS = Quantity(magnitude=6.371e6, unit="m")
ORBIT_RADIUS = Quantity(magnitude=6.771e6, unit="m")  # ~400 km altitude
EVERYDAY_MASS = Quantity(magnitude=1000.0, unit="kg")  # the two masses a metre apart
EVERYDAY_SEPARATION = Quantity(magnitude=1.0, unit="m")


def earth_gravity_chain() -> dict[str, float]:
    """Return the surface gravity, the gravitational parameter, the low-orbit speed, and
    the pull between two everyday masses a metre apart."""
    g = surface_gravity(mass=EARTH_MASS, radius=EARTH_RADIUS)
    mu = gravitational_parameter(mass=EARTH_MASS)
    v = circular_orbit_velocity(gravitational_parameter=mu, orbital_radius=ORBIT_RADIUS)
    everyday = gravitational_force(
        mass1=EVERYDAY_MASS, mass2=EVERYDAY_MASS, separation=EVERYDAY_SEPARATION
    )
    return {
        "surface_gravity_m_s2": g.to("m/s**2").magnitude,
        "gravitational_parameter_m3_s2": mu.to("m**3/s**2").magnitude,
        "low_orbit_speed_m_s": v.to("m/s").magnitude,
        "everyday_pull_n": everyday.to("N").magnitude,
    }


def main() -> None:
    d = earth_gravity_chain()
    print(f"surface gravity: {d['surface_gravity_m_s2']:.2f} m/s^2")
    print(f"gravitational parameter: {d['gravitational_parameter_m3_s2']:.4e} m^3/s^2")
    print(f"low-orbit speed (400 km): {d['low_orbit_speed_m_s']:.0f} m/s")
    print(f"pull between two 1,000 kg masses a metre apart: {d['everyday_pull_n']:.2e} N")


if __name__ == "__main__":
    main()
