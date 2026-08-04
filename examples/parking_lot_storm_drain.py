"""Worked example: sizing a storm channel for a parking lot — from rainfall to the flow it carries.

Drainage design runs in two steps that chain together. First, how much water arrives: the rational
method Q = C·i·A turns a design storm into a peak runoff, from the catchment area, the rainfall
intensity, and a runoff coefficient that says how much of the rain runs off rather than soaks in.
Second, whether the channel can carry it: Manning's equation gives the discharge a channel of a
given shape, slope, and roughness moves at a chosen depth. This example takes a 0.8-hectare asphalt
parking lot (runoff coefficient 0.9) under a 60 mm/hr storm, finds the peak runoff, and then checks
a proposed concrete-lined trapezoidal swale against it — confirming the swale running at its design
depth carries more than the storm delivers. The rational method sets the target; Manning proves the
channel meets it.

Run it directly (``python examples/parking_lot_storm_drain.py``);
:func:`drainage_check` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    manning_flow_rate,
    rational_method_peak_runoff,
    trapezoidal_channel_properties,
)
from anvilate.units import Quantity

RUNOFF_COEFFICIENT = 0.9  # asphalt
RAINFALL_INTENSITY = Quantity.parse("60 mm/hour")
CATCHMENT_AREA = Quantity.parse("8000 m**2")  # 0.8 ha

# A concrete-lined trapezoidal swale at its design depth.
SWALE_BOTTOM_WIDTH = Quantity.parse("0.4 m")
SWALE_DEPTH = Quantity.parse("0.2 m")
SWALE_SIDE_SLOPE = 1.0  # horizontal : vertical
CHANNEL_SLOPE = 0.01  # 1%
MANNING_N = 0.013  # concrete


def drainage_check() -> dict[str, float]:
    """Return the peak runoff and the swale's capacity (m³/s), and whether it is adequate."""
    peak = rational_method_peak_runoff(
        runoff_coefficient=RUNOFF_COEFFICIENT,
        rainfall_intensity=RAINFALL_INTENSITY,
        drainage_area=CATCHMENT_AREA,
    )
    props = trapezoidal_channel_properties(
        bottom_width=SWALE_BOTTOM_WIDTH, depth=SWALE_DEPTH, side_slope=SWALE_SIDE_SLOPE
    )
    capacity = manning_flow_rate(
        roughness_coefficient=MANNING_N,
        flow_area=props["area"],
        hydraulic_radius=props["hydraulic_radius"],
        channel_slope=CHANNEL_SLOPE,
    )
    peak_q = peak.to("m**3/s").magnitude
    cap_q = capacity.to("m**3/s").magnitude
    return {
        "peak_runoff_m3s": peak_q,
        "swale_capacity_m3s": cap_q,
        "capacity_margin": cap_q / peak_q,
    }


def main() -> None:
    d = drainage_check()
    print(f"peak runoff (rational method) : {d['peak_runoff_m3s']:.3f} m³/s")
    print(f"swale capacity (Manning)      : {d['swale_capacity_m3s']:.3f} m³/s")
    verdict = "adequate" if d["capacity_margin"] >= 1 else "UNDERSIZED"
    print(f"  -> {verdict}: the swale carries {d['capacity_margin']:.1f}x the storm's peak flow")


if __name__ == "__main__":
    main()
