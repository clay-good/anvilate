"""Worked example: sizing a real (trapezoidal) irrigation canal, not a textbook rectangle.

Textbook channel problems are rectangular because the geometry is trivial, but a real earthen
canal is trapezoidal — its banks slope back so they don't cave in. That sloped geometry changes
the flow area and the wetted perimeter, and getting them right is the difference between a canal
that carries the design flow and one that overtops. This example builds the flow geometry of a
trapezoidal canal (3 m bottom, 1.2 m deep, 1.5:1 banks), feeds its area and hydraulic radius
straight into Manning's equation, and reports the discharge and the Froude number — checking both
that the canal carries its 5 m³/s design flow and that it does so subcritically, so it won't scour.
It is the same two-question check as a rectangular channel, but on the section a canal is actually
dug to.

Run it directly (``python examples/trapezoidal_canal_capacity.py``);
:func:`canal_capacity` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    froude_number,
    manning_flow_rate,
    manning_flow_velocity,
    trapezoidal_channel_properties,
)
from anvilate.units import Quantity

BOTTOM_WIDTH = Quantity.parse("3 m")
DEPTH = Quantity.parse("1.2 m")
SIDE_SLOPE = 1.5  # 1.5 horizontal : 1 vertical banks
ROUGHNESS = 0.025  # Manning n, earthen canal in good condition
SLOPE = 0.001
DESIGN_FLOW = Quantity.parse("5 m**3/s")


def canal_capacity() -> dict[str, float]:
    """Return the discharge (m³/s), velocity (m/s), and Froude number of the trapezoidal canal."""
    geom = trapezoidal_channel_properties(
        bottom_width=BOTTOM_WIDTH, depth=DEPTH, side_slope=SIDE_SLOPE
    )
    discharge = (
        manning_flow_rate(
            roughness_coefficient=ROUGHNESS,
            flow_area=geom["area"],
            hydraulic_radius=geom["hydraulic_radius"],
            channel_slope=SLOPE,
        )
        .to("m**3/s")
        .magnitude
    )
    velocity = manning_flow_velocity(
        roughness_coefficient=ROUGHNESS,
        hydraulic_radius=geom["hydraulic_radius"],
        channel_slope=SLOPE,
    )
    # Hydraulic depth for the Froude number is area / top width.
    hydraulic_depth = Quantity(
        magnitude=geom["area"].to("m**2").magnitude / geom["top_width"].to("m").magnitude,
        unit="m",
    )
    froude = froude_number(velocity=velocity, hydraulic_depth=hydraulic_depth)
    return {
        "discharge_m3s": discharge,
        "velocity_ms": velocity.to("m/s").magnitude,
        "froude": froude,
    }


def main() -> None:
    c = canal_capacity()
    design = DESIGN_FLOW.to("m**3/s").magnitude
    cap_ok = "PASS" if c["discharge_m3s"] >= design else "FAIL"
    print(f"capacity : Q = {c['discharge_m3s']:.2f} m3/s vs {design:.1f} m3/s design  ({cap_ok})")
    print(f"velocity : {c['velocity_ms']:.2f} m/s")
    regime = "subcritical" if c["froude"] < 1.0 else "supercritical"
    print(f"regime   : Fr = {c['froude']:.2f} -> {regime} (won't scour)")


if __name__ == "__main__":
    main()
