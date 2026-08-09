"""Worked example: sizing a primary clarifier, and why the overflow rate IS a settling velocity.

A settling basin is sized by three hydraulic loadings, not by guesswork. This example takes a small
works treating 12,000 m³/day in a 30 m × 8 m rectangular clarifier 3 m deep, with 50 m of effluent
weir, and works out the retention time, the surface overflow rate, and the weir loading. The key
insight the numbers make concrete: the surface overflow rate is a velocity (about 0.58 mm/s here),
and it is exactly the settling velocity a particle must beat to be captured — so comparing it with
the Stokes settling velocity of the design particle tells you, directly, whether that particle is
removed.

At 12,000 m³/day the basin holds the water about 1.4 hours, presents an overflow rate near
50 m³/m²·day (a typical primary-clarifier value), and loads its weir at 240 m³/m·day (within the
usual 250 limit). Drop the flow and all three ease; shrink the surface and the overflow rate climbs
until fine particles start to escape.

Run it directly (``python examples/clarifier_primary_sizing.py``);
:func:`clarifier_loadings` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    hydraulic_retention_time,
    surface_overflow_rate,
    weir_loading_rate,
)
from anvilate.units import Quantity

FLOW = Quantity.parse("12000 m**3/day")
LENGTH = Quantity.parse("30 m")
WIDTH = Quantity.parse("8 m")
DEPTH = Quantity.parse("3 m")
WEIR_LENGTH = Quantity.parse("50 m")


def clarifier_loadings() -> dict[str, float]:
    """Return the retention time (h), overflow rate (m/day and mm/s), and weir loading (m²/day)."""
    volume = Quantity(magnitude=30.0 * 8.0 * 3.0, unit="m**3")
    surface = Quantity(magnitude=30.0 * 8.0, unit="m**2")
    hrt = hydraulic_retention_time(volume=volume, flow_rate=FLOW)
    sor = surface_overflow_rate(flow_rate=FLOW, surface_area=surface)
    wlr = weir_loading_rate(flow_rate=FLOW, weir_length=WEIR_LENGTH)
    return {
        "retention_time_h": hrt.to("hour").magnitude,
        "overflow_rate_m_day": sor.to("m/day").magnitude,
        "overflow_rate_mm_s": sor.to("mm/s").magnitude,
        "weir_loading_m2_day": wlr.to("m**2/day").magnitude,
    }


def main() -> None:
    c = clarifier_loadings()
    print("primary clarifier, 12,000 m3/day, 30 m x 8 m x 3 m, 50 m weir:")
    print(f"  retention time   : {c['retention_time_h']:.2f} h")
    print(
        f"  overflow rate    : {c['overflow_rate_m_day']:.0f} m3/m2.day "
        f"(= {c['overflow_rate_mm_s']:.2f} mm/s, the capture settling velocity)"
    )
    print(f"  weir loading     : {c['weir_loading_m2_day']:.0f} m3/m.day")


if __name__ == "__main__":
    main()
