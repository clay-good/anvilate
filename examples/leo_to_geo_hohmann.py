"""Worked example: the cheapest way from low orbit to geostationary — the Hohmann transfer.

Moving a spacecraft from one circular orbit to a higher one is not done in a single push. The most
propellant-efficient maneuver is the Hohmann transfer: one burn to stretch the orbit into an ellipse
that just touches the target altitude, a long coast up to that point, then a second burn to
circularize there. Two burns, a half-ellipse of coasting between them, and no wasted velocity — it
is the baseline every mission planner compares against, and its total Δv is what sizes the stage or
the satellite's own thrusters.

This example transfers from a 400 km low Earth orbit (radius 6771 km) to geostationary altitude
(radius 42164 km), around Earth (μ = 3.986e14 m³/s²). The first burn adds about 2.40 km/s to leave
LEO onto the transfer ellipse; the spacecraft then coasts for about 5.3 hours out to geostationary
radius; and the second burn adds about 1.46 km/s to circularize. The total transfer cost is about
3.86 km/s of Δv — the number a satellite must budget propellant for on top of reaching LEO. The
example reports the two burns, their sum, and the transfer time, so the maneuver's velocity and time
budget are explicit.

Run it directly (``python examples/leo_to_geo_hohmann.py``);
:func:`hohmann_transfer` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    hohmann_first_burn_delta_v,
    hohmann_second_burn_delta_v,
    hohmann_transfer_time,
)
from anvilate.units import Quantity

EARTH_MU = Quantity.parse("3.986e14 m**3/s**2")
LEO_RADIUS = Quantity.parse("6771 km")  # 400 km altitude
GEO_RADIUS = Quantity.parse("42164 km")  # geostationary


def hohmann_transfer() -> dict[str, float]:
    """Return the two Hohmann burns, their total, and the coast time for LEO -> GEO."""
    dv1 = hohmann_first_burn_delta_v(
        gravitational_parameter=EARTH_MU, initial_radius=LEO_RADIUS, final_radius=GEO_RADIUS
    )
    dv2 = hohmann_second_burn_delta_v(
        gravitational_parameter=EARTH_MU, initial_radius=LEO_RADIUS, final_radius=GEO_RADIUS
    )
    t = hohmann_transfer_time(
        gravitational_parameter=EARTH_MU, initial_radius=LEO_RADIUS, final_radius=GEO_RADIUS
    )
    dv1_kms = dv1.to("km/s").magnitude
    dv2_kms = dv2.to("km/s").magnitude
    return {
        "first_burn_km_s": dv1_kms,
        "second_burn_km_s": dv2_kms,
        "total_delta_v_km_s": dv1_kms + dv2_kms,
        "transfer_time_hours": t.to("s").magnitude / 3600.0,
    }


def main() -> None:
    d = hohmann_transfer()
    print(f"first burn (leave LEO): {d['first_burn_km_s']:.2f} km/s")
    print(f"second burn (circularize at GEO): {d['second_burn_km_s']:.2f} km/s")
    print(f"total transfer Δv: {d['total_delta_v_km_s']:.2f} km/s")
    print(f"coast time on the transfer ellipse: {d['transfer_time_hours']:.1f} hours")


if __name__ == "__main__":
    main()
