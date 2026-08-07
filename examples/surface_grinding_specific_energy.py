"""Worked example: why grinding is a finishing process — the surface has to shed the heat.

Grinding removes metal with thousands of microscopic abrasive grits, and that microscopy is its
defining trait: each grit peels a chip only a fraction of a micron thick, rubbing and ploughing as
much as cutting. The consequence is a specific energy — the work spent per unit volume removed — an
order of magnitude above turning or milling, and nearly all of it lands as heat in a thin surface
layer. That is why grinding governs on temperature, not force: push the throughput and the surface
burns, re-tempers, and picks up residual tensile stress long before the machine runs out of power.

This example runs a surface-grinding pass: a 0.02 mm infeed, a 200 mm/s table feed, a 30 m/s wheel,
20 mm wide, drawing 2.4 kW at the wheel. The specific removal rate works out to 4 mm³ per mm of
width per second, the equivalent chip thickness to about 0.13 microns — the sliver each pass peels,
which is what tracks grain force and the onset of burn. The specific energy is 30 J/mm³: roughly
ten times a turning cut of the same steel, and the number that, at this throughput, decides how much
heat the coolant and the workpiece must carry away. Double the wheel speed and the chip thins, the
grains cut cooler, and the same metal comes off with less thermal risk — the reason production
grinding runs the wheel fast. The example reports all three so the heat budget is explicit.

Run it directly (``python examples/surface_grinding_specific_energy.py``);
:func:`grinding_pass` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    grinding_equivalent_chip_thickness,
    grinding_specific_energy,
    grinding_specific_removal_rate,
)
from anvilate.units import Quantity

DEPTH_OF_CUT = Quantity.parse("0.02 mm")  # wheel infeed per pass
WORKPIECE_SPEED = Quantity.parse("200 mm/s")  # table feed
WHEEL_SPEED = Quantity.parse("30 m/s")  # wheel peripheral speed
WHEEL_WIDTH = Quantity.parse("20 mm")  # width in contact
POWER = Quantity.parse("2400 W")  # spindle power at the wheel


def grinding_pass() -> dict[str, float]:
    """Return the specific removal rate, equivalent chip thickness, and specific energy."""
    q = grinding_specific_removal_rate(depth_of_cut=DEPTH_OF_CUT, workpiece_speed=WORKPIECE_SPEED)
    h_eq = grinding_equivalent_chip_thickness(specific_removal_rate=q, wheel_speed=WHEEL_SPEED)
    h_eq_fast = grinding_equivalent_chip_thickness(
        specific_removal_rate=q, wheel_speed=Quantity.parse("60 m/s")
    )
    u = grinding_specific_energy(power=POWER, specific_removal_rate=q, wheel_width=WHEEL_WIDTH)
    return {
        "specific_removal_rate_mm2_s": q.to("mm**2/s").magnitude,
        "equivalent_chip_thickness_um": h_eq.to("micrometer").magnitude,
        "equivalent_chip_thickness_fast_um": h_eq_fast.to("micrometer").magnitude,
        "specific_energy_j_mm3": u.to("J/mm**3").magnitude,
    }


def main() -> None:
    d = grinding_pass()
    print(f"specific removal rate Q'_w: {d['specific_removal_rate_mm2_s']:.1f} mm^3/(mm*s)")
    print(
        f"equivalent chip thickness h_eq: {d['equivalent_chip_thickness_um']:.3f} um "
        f"(-> {d['equivalent_chip_thickness_fast_um']:.3f} um at a 60 m/s wheel)"
    )
    print(
        f"specific energy u: {d['specific_energy_j_mm3']:.0f} J/mm^3 "
        f"(~10x a turning cut -> grinding governs on heat, not force)"
    )


if __name__ == "__main__":
    main()
