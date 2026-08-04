"""Worked example: how a sheet of shiny foil becomes a radiation insulator.

Radiant heat between two facing surfaces does not care much about the air gap — it is a fourth-power
exchange through the surfaces' emissivities, and that is the lever a radiant barrier pulls. A hot
furnace wall at 800 K faces a cooler workshop wall at 400 K, a square metre of each, close enough to
see only one another (view factor 1). The question is what the cooler surface is made of.

A bare steel wall (emissivity 0.8) soaks up nearly everything the furnace throws at it and the two
exchange ~14.5 kW. Face the furnace with a polished-aluminum radiant barrier instead (emissivity
0.05) and the exchange collapses to ~1.1 kW — a thirteenfold cut — because a low-emissivity surface
both radiates little and reflects most of what lands on it. Nothing changed but one surface's
finish; no extra temperature drop, no bulk insulation. The lesson is that against radiation, a low-e
surface is worth more than inches of fiber, and the two-surface exchange is what quantifies it.

Run it directly (``python examples/radiant_barrier_shield.py``);
:func:`barrier_comparison` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import radiation_two_surface_exchange
from anvilate.units import Quantity

HOT_WALL_EMISSIVITY = 0.8
HOT_WALL_TEMPERATURE = Quantity.parse("800 K")
COOL_WALL_TEMPERATURE = Quantity.parse("400 K")
AREA = Quantity.parse("1 m**2")
VIEW_FACTOR = 1.0

BARE_STEEL_EMISSIVITY = 0.8
POLISHED_ALUMINUM_EMISSIVITY = 0.05


def barrier_comparison() -> dict[str, float]:
    """Return the radiant exchange (W) for a bare-steel and a low-emissivity cooler surface."""

    def exchange(cool_emissivity: float) -> float:
        return (
            radiation_two_surface_exchange(
                emissivity_1=HOT_WALL_EMISSIVITY,
                area_1=AREA,
                temperature_1=HOT_WALL_TEMPERATURE,
                emissivity_2=cool_emissivity,
                area_2=AREA,
                temperature_2=COOL_WALL_TEMPERATURE,
                view_factor=VIEW_FACTOR,
            )
            .to("W")
            .magnitude
        )

    return {
        "bare_steel_w": exchange(BARE_STEEL_EMISSIVITY),
        "radiant_barrier_w": exchange(POLISHED_ALUMINUM_EMISSIVITY),
    }


def main() -> None:
    c = barrier_comparison()
    ratio = c["bare_steel_w"] / c["radiant_barrier_w"]
    print(f"bare steel wall (e=0.80)   : {c['bare_steel_w'] / 1000:.1f} kW radiant exchange")
    print(f"radiant barrier (e=0.05)   : {c['radiant_barrier_w'] / 1000:.2f} kW radiant exchange")
    print(f"  -> the shiny barrier cuts the radiant load {ratio:.0f}x, adding no bulk insulation")


if __name__ == "__main__":
    main()
