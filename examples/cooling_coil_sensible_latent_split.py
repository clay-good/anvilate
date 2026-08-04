"""Worked example: splitting a cooling coil's load into sensible and latent, and why SHR matters.

A cooling coil does two jobs at once — it lowers the air temperature (sensible) and it wrings water
out of it (latent) — and a total-load number hides which one dominates. This example takes an air
handler moving 2 kg/s of dry air, cooling it 8°C while stripping 1.3 g of moisture per kg, and
splits the load: the sensible part from the temperature drop, the latent part from the moisture
removed, and the sensible heat ratio SHR that says how the coil's effort divides. Here the split is
roughly 0.7 sensible, a typical comfort-cooling ratio. The SHR is the number a designer matches to
the space: a coil with too high an SHR cannot pull enough moisture out (a humid room), and one with
too low an SHR overcools to dehumidify and then wastes energy reheating — so getting the split
right, not just the total, is what makes an HVAC system comfortable and efficient.

Run it directly (``python examples/cooling_coil_sensible_latent_split.py``);
:func:`coil_load_split` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import latent_heat_load, sensible_heat_load, sensible_heat_ratio
from anvilate.units import Quantity

DRY_AIR_FLOW = Quantity.parse("2 kg/s")
TEMPERATURE_DROP = Quantity.parse("8 K")
MEAN_HUMIDITY_RATIO = 0.010  # kg water / kg dry air
MOISTURE_REMOVED = 0.0013  # change in humidity ratio


def coil_load_split() -> dict[str, float]:
    """Return the sensible and latent loads (kW) and the sensible heat ratio."""
    sensible = sensible_heat_load(
        dry_air_mass_flow=DRY_AIR_FLOW,
        temperature_change=TEMPERATURE_DROP,
        humidity_ratio=MEAN_HUMIDITY_RATIO,
    )
    latent = latent_heat_load(
        dry_air_mass_flow=DRY_AIR_FLOW, humidity_ratio_change=MOISTURE_REMOVED
    )
    shr = sensible_heat_ratio(sensible_load=sensible, latent_load=latent)
    return {
        "sensible_kw": sensible.to("kW").magnitude,
        "latent_kw": latent.to("kW").magnitude,
        "shr": shr,
    }


def main() -> None:
    c = coil_load_split()
    total = c["sensible_kw"] + c["latent_kw"]
    print(f"sensible load : {c['sensible_kw']:.1f} kW (temperature drop)")
    print(f"latent load   : {c['latent_kw']:.1f} kW (moisture removed)")
    print(f"total load    : {total:.1f} kW,  SHR = {c['shr']:.2f}")
    print("  -> match the coil's SHR to the space's; the total alone won't keep it comfortable")


if __name__ == "__main__":
    main()
