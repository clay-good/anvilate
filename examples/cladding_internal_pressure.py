"""Worked example: the roof corner that peels off because a window broke.

The wind pressure that sizes a whole building's frame is not the pressure that sizes a single roof
panel or its fasteners. Components and cladding are designed for the *net* across their thickness —
the external suction on top minus the internal pressure underneath — and the internal part is where
buildings get caught out. ASCE 7 writes it p = qh·(GCp − GCpi): the external coefficient GCp peaks
in suction at corners and eaves, and the internal GCpi is ±0.18 for an enclosed building but jumps
to ±0.55 once the envelope is breached — a broken window or open door pressurizes the interior.

This example takes a roof-corner panel at 1.3 kPa velocity pressure with a strong GCp of −1.4. Kept
enclosed, the governing net suction (external suction plus the worst-sign internal 0.18) is about
2.05 kPa. Let one big window fail on the windward wall and the building becomes partially enclosed:
the internal coefficient balloons to 0.55, and the same panel now sees about 2.53 kPa of suction —
roughly 25% more, often past what the original fasteners were sized for, which is why cladding
failures cascade from a single broken opening. The lesson is that the internal pressure is not a
footnote: on components and cladding it can be the difference between a roof that stays on and one
that unzips from the corner in.

Run it directly (``python examples/cladding_internal_pressure.py``);
:func:`corner_panel_suction` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import components_cladding_net_pressure
from anvilate.units import Quantity

VELOCITY_PRESSURE = Quantity.parse("1.3 kPa")
CORNER_EXTERNAL_COEFFICIENT = -1.4  # GCp, roof corner zone (strong suction)
ENCLOSED_INTERNAL = 0.18  # GCpi, enclosed building
PARTIALLY_ENCLOSED_INTERNAL = 0.55  # GCpi, after the envelope is breached


def corner_panel_suction() -> dict[str, float]:
    """Return the governing net suction (kPa) on the corner panel, enclosed vs breached."""

    def governing(internal_magnitude: float) -> float:
        # The two signs of GCpi give two net pressures; suction governs at the larger magnitude.
        both = [
            components_cladding_net_pressure(
                velocity_pressure=VELOCITY_PRESSURE,
                external_pressure_coefficient=CORNER_EXTERNAL_COEFFICIENT,
                internal_pressure_coefficient=gcpi,
            )
            .to("kPa")
            .magnitude
            for gcpi in (internal_magnitude, -internal_magnitude)
        ]
        return min(both)  # most negative = worst suction

    return {
        "enclosed_kpa": governing(ENCLOSED_INTERNAL),
        "breached_kpa": governing(PARTIALLY_ENCLOSED_INTERNAL),
    }


def main() -> None:
    s = corner_panel_suction()
    worse = (s["breached_kpa"] / s["enclosed_kpa"] - 1.0) * 100.0
    print(f"enclosed building  : {s['enclosed_kpa']:.2f} kPa net suction on the corner panel")
    print(f"one window breaks  : {s['breached_kpa']:.2f} kPa ({worse:.0f}% worse)")
    print("  -> internal pressure, not the external gust, is what unzips cladding from a corner")


if __name__ == "__main__":
    main()
