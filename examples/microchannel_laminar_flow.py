"""Worked example: sizing a microfluidic channel with the Hagen-Poiseuille law.

Flow in a small tube at low speed is laminar, and the Hagen-Poiseuille law gives its rate exactly —
no friction factor or empirical constant needed. Because the flow depends on the fourth power of the
radius, microfluidic and capillary design is dominated by bore: a tiny channel needs a big pressure
to move even a trickle. This example runs the law forward (flow from pressure) and inverts it two
ways (the pressure a target flow needs, and the radius that would pass it).

The channel is a 100 micron radius tube, 50 mm long, carrying water (viscosity 1 mPa·s) under a
10 kPa drop. The Hagen-Poiseuille flow is about 7.9 microlitres per second. To instead push a fixed
1 microlitre per second through the same channel takes only about 1.3 kPa. And if the design fixes
that 1 microlitre per second under the original 10 kPa, the channel radius can shrink to about 60
microns — the quarter-power inverse barely moves the bore. The example reports the flow at 10 kPa,
the pressure for 1 uL/s, and the radius for 1 uL/s at 10 kPa.

Run it directly (``python examples/microchannel_laminar_flow.py``);
:func:`size_microchannel` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    hagen_poiseuille_flow_rate,
    hagen_poiseuille_pressure_drop,
    hagen_poiseuille_radius_for_flow,
)
from anvilate.units import Quantity

RADIUS = Quantity.parse("100 um")
LENGTH = Quantity.parse("50 mm")
VISCOSITY = Quantity.parse("0.001 Pa*s")
PRESSURE_DROP = Quantity.parse("10 kPa")
TARGET_FLOW = Quantity.parse("1 uL/s")


def size_microchannel() -> dict[str, float]:
    """Return the flow at 10 kPa, the pressure for 1 uL/s, and the radius for 1 uL/s at 10 kPa."""
    flow = hagen_poiseuille_flow_rate(
        pressure_drop=PRESSURE_DROP, radius=RADIUS, viscosity=VISCOSITY, length=LENGTH
    )
    pressure = hagen_poiseuille_pressure_drop(
        flow_rate=TARGET_FLOW, radius=RADIUS, viscosity=VISCOSITY, length=LENGTH
    )
    radius = hagen_poiseuille_radius_for_flow(
        flow_rate=TARGET_FLOW, pressure_drop=PRESSURE_DROP, viscosity=VISCOSITY, length=LENGTH
    )
    return {
        "flow_at_10kpa_ul_s": flow.to("uL/s").magnitude,
        "pressure_for_1ul_s_kpa": pressure.to("kPa").magnitude,
        "radius_for_1ul_s_um": radius.to("um").magnitude,
    }


def main() -> None:
    d = size_microchannel()
    print(f"flow at 10 kPa: {d['flow_at_10kpa_ul_s']:.1f} uL/s")
    print(f"pressure for 1 uL/s: {d['pressure_for_1ul_s_kpa']:.1f} kPa")
    print(f"radius for 1 uL/s at 10 kPa: {d['radius_for_1ul_s_um']:.0f} um")


if __name__ == "__main__":
    main()
