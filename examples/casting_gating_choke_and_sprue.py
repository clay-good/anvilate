"""Worked example: sizing a casting gate — the choke sets fill time, the taper keeps air out.

A gating system has two jobs that pull in opposite directions. It must fill the mold fast enough
that the metal does not freeze before the cavity is full, which argues for a big choke; and it must
fill smoothly, without sucking in air or shearing off oxide films, which argues for a slow, steady
stream. The design reconciles them at the choke — the smallest cross-section — sized so the fill
time lands in the alloy's safe window, with every other channel scaled from it. Then the sprue that
feeds the choke must be tapered: a straight sprue lets the accelerating stream neck away from the
walls and aspirate air, so the walls are cut to follow the stream down.

This example gates a 2000 cm³ iron casting under a 200 mm sprue head with a discharge coefficient
of 0.8. Aiming to fill in 5 seconds, inverting the fill-time relation calls for a choke of ~252 mm².
Check it back: metal leaves that choke at the Torricelli velocity of the 200 mm head and fills the
cavity in the target 5 s. The sprue runs from a 20 mm basin head down to a 220 mm base, so to stay
full it tapers to an area ratio of about 3.3 (wide at the top, narrow at the base). The example
reports the choke area, the fill time it produces, and the sprue taper ratio, so the two halves of a
sound gate — throughput and anti-aspiration — are explicit.

Run it directly (``python examples/casting_gating_choke_and_sprue.py``);
:func:`gating_design` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    gating_choke_area,
    gating_fill_time,
    sprue_taper_ratio,
)
from anvilate.units import Quantity

CASTING_VOLUME = Quantity.parse("2000 cm**3")
SPRUE_HEAD = Quantity.parse("0.2 m")
DISCHARGE_COEFFICIENT = 0.8
TARGET_FILL_TIME = Quantity.parse("5 s")
BASIN_HEAD = Quantity.parse("0.02 m")
SPRUE_BASE_HEAD = Quantity.parse("0.22 m")


def gating_design() -> dict[str, float]:
    """Return the choke area for the target time, the fill time it gives, and the sprue taper."""
    choke = gating_choke_area(
        casting_volume=CASTING_VOLUME,
        fill_time=TARGET_FILL_TIME,
        effective_head=SPRUE_HEAD,
        discharge_coefficient=DISCHARGE_COEFFICIENT,
    )
    fill_time = gating_fill_time(
        casting_volume=CASTING_VOLUME,
        choke_area=choke,
        effective_head=SPRUE_HEAD,
        discharge_coefficient=DISCHARGE_COEFFICIENT,
    )
    taper = sprue_taper_ratio(top_head=BASIN_HEAD, bottom_head=SPRUE_BASE_HEAD)
    return {
        "choke_area_mm2": choke.to("mm**2").magnitude,
        "fill_time_s": fill_time.to("s").magnitude,
        "sprue_taper_ratio": taper,
    }


def main() -> None:
    d = gating_design()
    print(f"choke area for a 5 s fill: {d['choke_area_mm2']:.0f} mm^2")
    print(f"fill time it produces: {d['fill_time_s']:.1f} s")
    print(
        f"sprue taper ratio (top/base): {d['sprue_taper_ratio']:.2f} "
        f"-> wide at top, narrow at base, to keep the stream full"
    )


if __name__ == "__main__":
    main()
