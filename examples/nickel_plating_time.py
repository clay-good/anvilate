"""Worked example: how long to nickel-plate a part to spec — Faraday's law sets the tank time.

Electroplating builds a coating by depositing metal from a bath, and the amount deposited is fixed
by the charge that flows: Faraday's law says the mass is proportional to current times time,
discounted by the current efficiency that some of the current wastes making hydrogen. That mass over
the part's area and it becomes a coating thickness, which is how a plating spec is written. So the
tank time to hit a target thickness follows directly — and the only fast way to cut it is to raise
the current, up to what the bath chemistry and the finish quality allow.

This example nickel-plates a part of 100 cm² wetted area to a 25 µm thickness at 10 A, with a bath
running at 95% current efficiency (nickel equivalent weight 29.34 g/equiv, density 8.9 g/cm³).
Inverting Faraday's law gives a tank time of about 12.8 minutes; over that time the deposit lays
down about 2.2 g of nickel. Check the thickness back out at that time and current — 25 µm, as spec.
The example reports the plating time, the mass deposited, and the thickness check, so the chain from
a coating spec to a line cycle time is explicit.

Run it directly (``python examples/nickel_plating_time.py``);
:func:`nickel_plating` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    electroplating_deposition_thickness,
    electroplating_mass_deposited,
    electroplating_time_for_thickness,
)
from anvilate.units import Quantity

NICKEL_EQUIVALENT_WEIGHT = 29.34  # g/equiv (58.69 / 2)
NICKEL_DENSITY = Quantity.parse("8.9 g/cm**3")
PLATED_AREA = Quantity.parse("100 cm**2")
CURRENT = Quantity.parse("10 A")
CURRENT_EFFICIENCY = 0.95
TARGET_THICKNESS = Quantity.parse("25 micrometer")


def nickel_plating() -> dict[str, float]:
    """Return the tank time for a 25 um coat, the mass deposited, and the thickness check."""
    time = electroplating_time_for_thickness(
        target_thickness=TARGET_THICKNESS,
        current=CURRENT,
        plated_area=PLATED_AREA,
        equivalent_weight=NICKEL_EQUIVALENT_WEIGHT,
        density=NICKEL_DENSITY,
        current_efficiency=CURRENT_EFFICIENCY,
    )
    mass = electroplating_mass_deposited(
        current=CURRENT,
        plating_time=time,
        equivalent_weight=NICKEL_EQUIVALENT_WEIGHT,
        current_efficiency=CURRENT_EFFICIENCY,
    )
    thickness = electroplating_deposition_thickness(
        current=CURRENT,
        plating_time=time,
        plated_area=PLATED_AREA,
        equivalent_weight=NICKEL_EQUIVALENT_WEIGHT,
        density=NICKEL_DENSITY,
        current_efficiency=CURRENT_EFFICIENCY,
    )
    return {
        "plating_time_min": time.to("min").magnitude,
        "mass_deposited_g": mass.to("g").magnitude,
        "thickness_check_um": thickness.to("micrometer").magnitude,
    }


def main() -> None:
    d = nickel_plating()
    print(f"tank time for a 25 um coat: {d['plating_time_min']:.1f} min")
    print(f"nickel deposited: {d['mass_deposited_g']:.2f} g")
    print(f"thickness check at that time: {d['thickness_check_um']:.1f} um -> matches the spec")


if __name__ == "__main__":
    main()
