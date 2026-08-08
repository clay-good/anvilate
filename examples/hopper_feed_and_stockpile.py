"""Worked example: sizing a hopper outlet to a feed rate, and a stockpile's capacity.

Granular material breaks two rules that liquids obey, and both matter to a bulk-handling plant. It
discharges from a hopper at a rate set almost entirely by the outlet size — not by how full the bin
is — so it empties at a steady rate right down to the last, and the Beverloo correlation predicts
that rate from the opening and the particle size. And when it is piled it does not spread flat but
stands at its angle of repose, forming a cone whose volume sets the stockpile's capacity.

This example handles a 1500 kg/m³ material of 5 mm particles. First, sizing a feeder: to discharge
about 10 kg/s, the Beverloo inverse calls for an outlet about 113 mm across (well above the few-
particle size at which it would arch and jam). Check it forward and a 113 mm opening indeed passes
roughly 10 kg/s, near-independent of the head above. Second, a stockpile poured to a 10 m base
radius at a 35° angle of repose stands about 7 m tall and holds about 733 m³ — around 1100 t at this
bulk density. The example reports the sized outlet, the rate it passes, and the stockpile volume, so
the feed-and-store chain of a bulk system is explicit.

Run it directly (``python examples/hopper_feed_and_stockpile.py``);
:func:`bulk_handling` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    beverloo_discharge_rate,
    beverloo_orifice_for_rate,
    conical_stockpile_volume,
)
from anvilate.units import Quantity

BULK_DENSITY = Quantity.parse("1500 kg/m**3")
PARTICLE_DIAMETER = Quantity.parse("5 mm")
TARGET_RATE = Quantity.parse("10 kg/s")
STOCKPILE_RADIUS = Quantity.parse("10 m")
ANGLE_OF_REPOSE = 35.0


def bulk_handling() -> dict[str, float]:
    """Return the sized outlet for a target feed, the rate it passes, and the stockpile volume."""
    outlet = beverloo_orifice_for_rate(
        mass_flow=TARGET_RATE,
        particle_diameter=PARTICLE_DIAMETER,
        bulk_density=BULK_DENSITY,
    )
    rate = beverloo_discharge_rate(
        orifice_diameter=outlet,
        particle_diameter=PARTICLE_DIAMETER,
        bulk_density=BULK_DENSITY,
    )
    volume = conical_stockpile_volume(base_radius=STOCKPILE_RADIUS, angle_of_repose=ANGLE_OF_REPOSE)
    volume_m3 = volume.to("m**3").magnitude
    tonnes = volume_m3 * BULK_DENSITY.to("kg/m**3").magnitude / 1000.0
    return {
        "outlet_diameter_mm": outlet.to("mm").magnitude,
        "discharge_rate_kg_s": rate.to("kg/s").magnitude,
        "stockpile_volume_m3": volume_m3,
        "stockpile_tonnes": tonnes,
    }


def main() -> None:
    d = bulk_handling()
    print(f"outlet for a 10 kg/s feed: {d['outlet_diameter_mm']:.0f} mm")
    print(f"rate that outlet passes: {d['discharge_rate_kg_s']:.1f} kg/s")
    print(
        f"stockpile at R=10 m, 35 deg repose: {d['stockpile_volume_m3']:.0f} m^3 "
        f"(~{d['stockpile_tonnes']:.0f} t)"
    )


if __name__ == "__main__":
    main()
