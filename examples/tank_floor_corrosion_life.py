"""Worked example: a storage-tank floor's corrosion rate and the remaining life it buys.

Asset integrity turns two field measurements into a retirement date. This example takes a steel
tank floor: a weighed corrosion coupon (8 g lost from a 50 cm² plate over a year) gives one
penetration rate by the ASTM G1 weight-loss method, and a linear-polarization probe reading
(18 µA/cm²) gives another by Faraday's law. The two methods should land in the same ballpark — a
useful cross-check. Taking the coupon rate as the design basis, the example then asks the question a
fitness-for-service assessment exists to answer: with the floor now 8 mm thick and a 3 mm retirement
minimum, how many years are left before it must be relined?

Run it directly (``python examples/tank_floor_corrosion_life.py``);
:func:`floor_assessment` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    corrosion_penetration_rate,
    faraday_corrosion_rate,
    remaining_wall_life,
)
from anvilate.units import Quantity

STEEL_DENSITY = Quantity.parse("7.87 g/cm**3")
STEEL_EQUIVALENT_WEIGHT = 27.9  # Fe, 2 electrons: 55.85 / 2


def floor_assessment() -> dict[str, float]:
    """Return the two penetration rates (mm/yr) and the remaining floor life (years)."""
    coupon_rate = corrosion_penetration_rate(
        mass_loss=Quantity.parse("8 g"),
        exposed_area=Quantity.parse("50 cm**2"),
        exposure_time=Quantity.parse("1 year"),
        density=STEEL_DENSITY,
    )
    probe_rate = faraday_corrosion_rate(
        corrosion_current_density=Quantity.parse("18 uA/cm**2"),
        equivalent_weight=STEEL_EQUIVALENT_WEIGHT,
        density=STEEL_DENSITY,
    )
    life = remaining_wall_life(
        current_thickness=Quantity.parse("8 mm"),
        minimum_thickness=Quantity.parse("3 mm"),
        corrosion_rate=coupon_rate,
    )
    return {
        "coupon_rate_mm_yr": coupon_rate.to("mm/year").magnitude,
        "probe_rate_mm_yr": probe_rate.to("mm/year").magnitude,
        "remaining_life_yr": life.to("year").magnitude,
    }


def main() -> None:
    a = floor_assessment()
    print(f"weight-loss coupon : {a['coupon_rate_mm_yr']:.3f} mm/yr")
    print(f"polarization probe : {a['probe_rate_mm_yr']:.3f} mm/yr (Faraday cross-check)")
    print(f"remaining life     : {a['remaining_life_yr']:.1f} yr (8 mm now, 3 mm retire)")
    print("  -> two independent methods, one rate; the thinning wall sets the reline date")


if __name__ == "__main__":
    main()
