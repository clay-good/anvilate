"""Worked example: does a concrete channel pass the design storm, and is the flow tranquil?

Sizing an open drainage channel is two questions, not one. First, capacity: can the section
carry the design discharge at the depth you've allowed? Manning's equation answers it from the
channel's shape, slope, and lining. Second, regime: is the flow subcritical (tranquil, safe to
run in a lined ditch) or supercritical (fast and shallow, prone to a hydraulic jump and scour)?
The Froude number decides, and it agrees with comparing the flow depth to the critical depth.
This example runs a 3 m wide rectangular concrete channel at 1 m depth on a 0.1% grade: it
carries 5.2 m³/s — comfortably over a 4.5 m³/s design storm — and the flow is subcritical, so
the design is both adequate and calm. The point is that a channel that passes on capacity can
still be the wrong design if its regime is wrong.

Run it directly (``python examples/drainage_channel_capacity.py``);
:func:`channel_check` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    critical_depth_rectangular,
    froude_number,
    hydraulic_radius,
    manning_flow_rate,
    manning_flow_velocity,
)
from anvilate.units import Quantity

WIDTH = Quantity.parse("3 m")
DEPTH = Quantity.parse("1 m")
ROUGHNESS = 0.013  # Manning n, smooth concrete
SLOPE = 0.001  # 0.1% bed grade
DESIGN_STORM = Quantity.parse("4.5 m**3/s")


def channel_check() -> dict[str, float]:
    """Return the discharge (m³/s), velocity (m/s), Froude number, and critical depth (m)."""
    b = WIDTH.to("m").magnitude
    y = DEPTH.to("m").magnitude
    area = Quantity(magnitude=b * y, unit="m**2")
    perimeter = Quantity(magnitude=b + 2 * y, unit="m")  # bed + two walls
    r = hydraulic_radius(flow_area=area, wetted_perimeter=perimeter)
    velocity = manning_flow_velocity(
        roughness_coefficient=ROUGHNESS, hydraulic_radius=r, channel_slope=SLOPE
    )
    discharge = manning_flow_rate(
        roughness_coefficient=ROUGHNESS, flow_area=area, hydraulic_radius=r, channel_slope=SLOPE
    )
    froude = froude_number(velocity=velocity, hydraulic_depth=DEPTH)
    y_c = critical_depth_rectangular(flow_rate=discharge, channel_width=WIDTH)
    return {
        "discharge_m3s": discharge.to("m**3/s").magnitude,
        "velocity_ms": velocity.to("m/s").magnitude,
        "froude": froude,
        "critical_depth_m": y_c.to("m").magnitude,
        "flow_depth_m": y,
    }


def main() -> None:
    c = channel_check()
    storm = DESIGN_STORM.to("m**3/s").magnitude
    cap_ok = "PASS" if c["discharge_m3s"] >= storm else "FAIL"
    print(f"capacity : Q = {c['discharge_m3s']:.2f} m3/s vs {storm:.2f} m3/s storm  ({cap_ok})")
    print(f"velocity : {c['velocity_ms']:.2f} m/s")
    regime = "subcritical (tranquil)" if c["froude"] < 1.0 else "supercritical (rapid)"
    print(f"regime   : Fr = {c['froude']:.2f} -> {regime}")
    print(
        f"           flow depth {c['flow_depth_m']:.2f} m vs critical {c['critical_depth_m']:.2f} m"
    )


if __name__ == "__main__":
    main()
