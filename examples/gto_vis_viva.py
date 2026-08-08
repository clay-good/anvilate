"""Worked example: how fast a spacecraft moves on an elliptical transfer orbit — the vis-viva law.

A spacecraft on an elliptical orbit does not travel at a constant speed. It races through its lowest
point (perigee) and crawls at its highest (apogee), trading kinetic for potential energy as it
climbs and back again as it falls. The vis-viva equation, v = √(μ(2/r − 1/a)), ties the speed at any
radius r to just two things: the gravitational parameter μ and the orbit's semi-major axis a, fixed
by the two extremes of the orbit. It is the single most useful relation in orbital mechanics, and
its sibling, the specific orbital energy ε = −μ/(2a), says at a glance whether the orbit is bound.

This example analyses a geostationary transfer orbit around Earth (μ = 3.986e14 m³/s²): perigee at a
6771 km radius (low Earth orbit) and apogee at 42164 km (geostationary). Averaging the apsides gives
a semi-major axis of 24468 km. The vis-viva law then gives about 10.07 km/s at perigee and only
1.62 km/s at apogee — the spacecraft moves more than six times faster low down than high up. The
specific energy comes out negative, about −8.1 MJ/kg, confirming the orbit is bound. The example
reports the semi-major axis, the perigee and apogee speeds, and the specific energy, so the speed
variation and the bound character of an elliptical orbit are explicit.

Run it directly (``python examples/gto_vis_viva.py``);
:func:`transfer_orbit` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    orbit_specific_energy,
    semi_major_axis_from_apsides,
    vis_viva_velocity,
)
from anvilate.units import Quantity

EARTH_MU = Quantity.parse("3.986e14 m**3/s**2")
PERIGEE_RADIUS = Quantity.parse("6771 km")  # low Earth orbit
APOGEE_RADIUS = Quantity.parse("42164 km")  # geostationary


def transfer_orbit() -> dict[str, float]:
    """Return the semi-major axis, perigee/apogee speeds, and specific energy of a GTO."""
    a = semi_major_axis_from_apsides(periapsis_radius=PERIGEE_RADIUS, apoapsis_radius=APOGEE_RADIUS)
    v_perigee = vis_viva_velocity(
        gravitational_parameter=EARTH_MU, radius=PERIGEE_RADIUS, semi_major_axis=a
    )
    v_apogee = vis_viva_velocity(
        gravitational_parameter=EARTH_MU, radius=APOGEE_RADIUS, semi_major_axis=a
    )
    energy = orbit_specific_energy(gravitational_parameter=EARTH_MU, semi_major_axis=a)
    return {
        "semi_major_axis_km": a.to("km").magnitude,
        "perigee_speed_km_s": v_perigee.to("km/s").magnitude,
        "apogee_speed_km_s": v_apogee.to("km/s").magnitude,
        "specific_energy_mj_kg": energy.to("J/kg").magnitude / 1.0e6,
    }


def main() -> None:
    d = transfer_orbit()
    print(f"semi-major axis: {d['semi_major_axis_km']:.0f} km")
    print(f"perigee speed: {d['perigee_speed_km_s']:.2f} km/s")
    print(f"apogee speed: {d['apogee_speed_km_s']:.2f} km/s (>6x slower than perigee)")
    print(f"specific energy: {d['specific_energy_mj_kg']:.1f} MJ/kg (negative -> bound orbit)")


if __name__ == "__main__":
    main()
