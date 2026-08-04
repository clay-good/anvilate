"""Worked example: why a thick busbar wastes copper at high frequency — the skin effect.

Alternating current does not flow evenly through a conductor; it crowds toward the surface, and the
depth at which it has mostly died away is the skin depth δ = √(ρ/(π·f·μ)). This example runs it for
a copper bar at three frequencies. At 60 Hz mains the skin depth is about 8.5 mm, so a bar up to a
centimetre or so thick still carries current through its whole section — thickness is not wasted.
Push the frequency to 10 kHz (an induction-heating or switching supply) and the skin depth collapses
to about 0.65 mm, and at 1 MHz to just 65 µm: the interior of a solid bar carries almost nothing, so
the copper there is dead weight. That is the reason high-frequency conductors are stranded into litz
wire or made hollow, and why induction heating warms only the surface of the work.

Run it directly (``python examples/busbar_skin_effect.py``);
:func:`copper_skin_depths` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import skin_depth
from anvilate.units import Quantity

COPPER_RESISTIVITY = Quantity.parse("1.68e-8 ohm*m")


def copper_skin_depths() -> dict[str, float]:
    """Return copper's skin depth (mm) at 60 Hz, 10 kHz, and 1 MHz."""
    return {
        "depth_mm_60hz": skin_depth(
            resistivity=COPPER_RESISTIVITY, frequency=Quantity.parse("60 Hz")
        )
        .to("mm")
        .magnitude,
        "depth_mm_10khz": skin_depth(
            resistivity=COPPER_RESISTIVITY, frequency=Quantity.parse("10 kHz")
        )
        .to("mm")
        .magnitude,
        "depth_mm_1mhz": skin_depth(
            resistivity=COPPER_RESISTIVITY, frequency=Quantity.parse("1 MHz")
        )
        .to("mm")
        .magnitude,
    }


def main() -> None:
    d = copper_skin_depths()
    print(f"copper skin depth @ 60 Hz  : {d['depth_mm_60hz']:.2f} mm (whole bar conducts)")
    print(f"copper skin depth @ 10 kHz : {d['depth_mm_10khz']:.2f} mm")
    print(
        f"copper skin depth @ 1 MHz  : {d['depth_mm_1mhz'] * 1000:.0f} µm (interior is dead weight)"
    )
    print("  -> skin depth falls as 1/√f; high-frequency conductors go stranded (litz) or hollow")


if __name__ == "__main__":
    main()
