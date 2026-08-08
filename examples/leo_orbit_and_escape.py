"""Worked example: how fast a low-Earth-orbit satellite flies, and what it takes to leave.

A satellite in a circular orbit is in perpetual free fall: gravity bends its path just enough that
it keeps missing the ground. The speed that balance requires, the time to circle once, and the extra
speed needed to break free of Earth entirely all follow from two numbers — Earth's gravitational
parameter μ = G·M and the orbital radius from Earth's center. The counter-intuitive part is that
lower orbits are faster, and escape is never far above orbital speed: it is always exactly √2 times
the circular speed, wherever you are.

This example puts a satellite in low Earth orbit at 400 km altitude — a radius of 6771 km from
Earth's center — with Earth's μ of 3.986e14 m³/s². The circular speed works out to about 7.67 km/s,
roughly Mach 23, and the orbit comes around once every 92 minutes, which is why a LEO satellite laps
the planet about sixteen times a day. To leave Earth from that altitude, escape velocity is about
10.85 km/s — only 41% more than the orbital speed already achieved, which is why interplanetary
missions depart from orbit rather than from the ground. The example reports the orbital speed, the
period, and the escape velocity, so the tight relationship among them is explicit.

Run it directly (``python examples/leo_orbit_and_escape.py``);
:func:`leo_orbit` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    circular_orbit_velocity,
    escape_velocity,
    orbital_period,
)
from anvilate.units import Quantity

EARTH_MU = Quantity.parse("3.986e14 m**3/s**2")
ORBIT_RADIUS = Quantity.parse("6771 km")  # 400 km altitude + 6371 km Earth radius


def leo_orbit() -> dict[str, float]:
    """Return the LEO orbital speed, the period, and the escape velocity at that radius."""
    v = circular_orbit_velocity(gravitational_parameter=EARTH_MU, orbital_radius=ORBIT_RADIUS)
    t = orbital_period(gravitational_parameter=EARTH_MU, orbital_radius=ORBIT_RADIUS)
    v_esc = escape_velocity(gravitational_parameter=EARTH_MU, orbital_radius=ORBIT_RADIUS)
    return {
        "orbital_speed_km_s": v.to("km/s").magnitude,
        "period_min": t.to("s").magnitude / 60.0,
        "escape_velocity_km_s": v_esc.to("km/s").magnitude,
    }


def main() -> None:
    d = leo_orbit()
    print(f"circular orbital speed: {d['orbital_speed_km_s']:.2f} km/s")
    print(f"orbital period: {d['period_min']:.0f} min (~{24 * 60 / d['period_min']:.0f} laps/day)")
    print(
        f"escape velocity: {d['escape_velocity_km_s']:.2f} km/s "
        f"(= sqrt(2) x orbital speed, only ~41% more)"
    )


if __name__ == "__main__":
    main()
