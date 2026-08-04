"""Worked example: reading a flow from an orifice plate, and sizing the transmitter for it.

An orifice plate is the cheapest way to meter pipe flow: squeeze the stream through a hole,
measure the pressure drop, and Bernoulli gives the flow. This example works both directions of
that relation on a 100 mm water line with a 50 mm orifice (β = 0.5). Forward: a measured 20 kPa
drop reads as about 7.8 L/s. Backward: to design the installation you fix the flow you want to
resolve — say a 12 L/s full-scale — and ask what pressure drop the plate will produce, so you
can pick the range of the differential-pressure transmitter. Because flow goes as the square
root of the drop, that full-scale flow lands at a much larger drop than the operating point, and
sizing the transmitter to it is what keeps the low end of the scale readable.

Run it directly (``python examples/orifice_meter_sizing.py``);
:func:`meter_readings` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    differential_pressure_for_flow,
    obstruction_meter_flow_rate,
)
from anvilate.units import Quantity

DISCHARGE_COEFFICIENT = 0.61  # sharp-edged orifice
THROAT_DIAMETER = Quantity.parse("50 mm")
PIPE_DIAMETER = Quantity.parse("100 mm")
DENSITY = Quantity.parse("1000 kg/m**3")  # water
OPERATING_DROP = Quantity.parse("20 kPa")
FULL_SCALE_FLOW = Quantity.parse("0.012 m**3/s")  # 12 L/s design full-scale


def meter_readings() -> dict[str, float]:
    """Return the operating flow (L/s) and the full-scale pressure drop (kPa)."""
    operating_flow = (
        obstruction_meter_flow_rate(
            discharge_coefficient=DISCHARGE_COEFFICIENT,
            throat_diameter=THROAT_DIAMETER,
            pipe_diameter=PIPE_DIAMETER,
            pressure_drop=OPERATING_DROP,
            density=DENSITY,
        )
        .to("m**3/s")
        .magnitude
    )
    full_scale_drop = (
        differential_pressure_for_flow(
            flow_rate=FULL_SCALE_FLOW,
            discharge_coefficient=DISCHARGE_COEFFICIENT,
            throat_diameter=THROAT_DIAMETER,
            pipe_diameter=PIPE_DIAMETER,
            density=DENSITY,
        )
        .to("kPa")
        .magnitude
    )
    return {
        "operating_flow_lps": operating_flow * 1000.0,
        "full_scale_flow_lps": FULL_SCALE_FLOW.to("m**3/s").magnitude * 1000.0,
        "full_scale_drop_kpa": full_scale_drop,
    }


def main() -> None:
    r = meter_readings()
    print(f"measured 20 kPa drop reads : {r['operating_flow_lps']:.1f} L/s")
    fs_flow = r["full_scale_flow_lps"]
    fs_drop = r["full_scale_drop_kpa"]
    print(f"for a {fs_flow:.0f} L/s full-scale : size the transmitter to {fs_drop:.0f} kPa")
    print("  (flow ~ sqrt(dp), so full-scale flow sits at a much larger drop)")


if __name__ == "__main__":
    main()
