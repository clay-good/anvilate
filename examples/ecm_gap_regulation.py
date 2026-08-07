"""Worked example: why an ECM cut cannot simply be fed faster — the gap regulates itself.

Electrochemical machining dissolves metal by Faraday's law, so it does not care how hard the metal
is: charge in, volume out. What it does care about is the balance between how fast the tool is fed
and how fast the electrolyte gap can supply current to dissolve metal at that rate. The gap is not
set by the operator; it settles on its own. Feed the tool in and the gap narrows, which — by Ohm's
law across the electrolyte — raises the current density and speeds dissolution until the etch rate
matches the feed. That self-regulation is the whole trick of ECM, and also its cliff edge: push the
feed past what the voltage and electrolyte can support and the gap collapses toward zero, the tool
touches the work, and the electrolyte arcs into a short that pits both faster than any cut.

This example machines steel (equivalent weight 27.9 g/equiv, density 7.87 g/cm³) at 15 V in an
electrolyte of 0.2 S/cm conductivity, drawing 1000 A over the frontal area at 100 A/cm². The removal
rate is about 2.2 cm³/min, and the corresponding feed rate is about 2.2 mm/min. At that feed the gap
settles at roughly 0.3 mm — comfortably clear. Double the feed and the equilibrium gap halves to
0.15 mm; keep pushing and it closes on the short-circuit limit. The example reports the removal
rate, the feed rate, and the equilibrium gap at the design feed and at double it, so the shrinking
gap that caps how hard ECM can be driven is explicit.

Run it directly (``python examples/ecm_gap_regulation.py``);
:func:`ecm_operating_point` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    ecm_equilibrium_gap,
    ecm_feed_rate,
    ecm_material_removal_rate,
)
from anvilate.units import Quantity

EQUIVALENT_WEIGHT = 27.9  # steel, g/equiv (atomic weight over electrons transferred)
DENSITY = Quantity.parse("7.87 g/cm**3")
TOTAL_CURRENT = Quantity.parse("1000 A")
CURRENT_DENSITY = Quantity.parse("100 A/cm**2")
CONDUCTIVITY = Quantity.parse("0.2 S/cm")
VOLTAGE = Quantity.parse("15 V")


def ecm_operating_point() -> dict[str, float]:
    """Return the removal rate, feed rate, and the equilibrium gap at the feed and at double it."""
    mrr = ecm_material_removal_rate(
        current=TOTAL_CURRENT, equivalent_weight=EQUIVALENT_WEIGHT, density=DENSITY
    )
    feed = ecm_feed_rate(
        current_density=CURRENT_DENSITY, equivalent_weight=EQUIVALENT_WEIGHT, density=DENSITY
    )
    gap = ecm_equilibrium_gap(
        electrolyte_conductivity=CONDUCTIVITY,
        applied_voltage=VOLTAGE,
        feed_rate=feed,
        equivalent_weight=EQUIVALENT_WEIGHT,
        density=DENSITY,
    )
    gap_double = ecm_equilibrium_gap(
        electrolyte_conductivity=CONDUCTIVITY,
        applied_voltage=VOLTAGE,
        feed_rate=Quantity(magnitude=2.0 * feed.to("mm/min").magnitude, unit="mm/min"),
        equivalent_weight=EQUIVALENT_WEIGHT,
        density=DENSITY,
    )
    return {
        "removal_rate_cm3_min": mrr.to("cm**3/min").magnitude,
        "feed_rate_mm_min": feed.to("mm/min").magnitude,
        "gap_mm": gap.to("mm").magnitude,
        "gap_double_feed_mm": gap_double.to("mm").magnitude,
    }


def main() -> None:
    d = ecm_operating_point()
    print(f"removal rate: {d['removal_rate_cm3_min']:.2f} cm^3/min")
    print(f"feed rate: {d['feed_rate_mm_min']:.2f} mm/min")
    print(
        f"equilibrium gap: {d['gap_mm']:.2f} mm "
        f"(halves to {d['gap_double_feed_mm']:.2f} mm at double the feed)"
    )
    print("  -> feed too fast and the gap closes to a short circuit")


if __name__ == "__main__":
    main()
