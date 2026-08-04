"""Worked example: a motor feeder screened for both voltage drop and ampacity, as one scorecard.

The electrical pack reports the two conditions a feeder must satisfy at once, and which one governs
depends on the run. This example feeds a 37 kW (≈50 HP) motor at 480 V and screens two conductor
choices. A 35 mm² run 100 m out passes comfortably on both counts. Pushing the same load 300 m on a
16 mm² conductor keeps the current within the wire's ampacity — the cable is not overloaded — yet
the voltage drop climbs past 5%, well over the 3% the NEC note recommends, so the motor at the
far end would see too little voltage to start reliably. It is the classic result that on a long run
the length, not the current, sizes the cable.

Run it directly (``python examples/motor_feeder_scorecard.py``);
:func:`feeder_scorecards` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.packs.electrical import Feeder, screen_feeder
from anvilate.units import Quantity

_LOAD = {
    "load_power": Quantity.parse("37 kW"),
    "power_factor": 0.85,
    "line_voltage": Quantity.parse("480 V"),
    "resistivity": Quantity.parse("1.68e-8 ohm*m"),
}


def feeder_scorecards() -> dict[str, str]:
    """Return the scorecard status for a short/fat run and a long/thin run of the same load."""
    short_run = Feeder(
        one_way_length=Quantity.parse("100 m"),
        conductor_area=Quantity.parse("35 mm**2"),
        conductor_ampacity=Quantity.parse("115 A"),
        **_LOAD,
    )
    long_run = Feeder(
        one_way_length=Quantity.parse("300 m"),
        conductor_area=Quantity.parse("16 mm**2"),
        conductor_ampacity=Quantity.parse("65 A"),
        **_LOAD,
    )
    short_card = screen_feeder(short_run)
    long_card = screen_feeder(long_run)
    return {
        "short_status": short_card.status.value,
        "long_status": long_card.status.value,
        "long_failures": ", ".join(e.name for e in long_card.failures()),
    }


def main() -> None:
    r = feeder_scorecards()
    print(f"100 m / 35 mm² : {r['short_status'].upper()}")
    print(f"300 m / 16 mm² : {r['long_status'].upper()} (fails: {r['long_failures']})")
    print("  -> the long run stays within ampacity but drops too much voltage; length sizes it")


if __name__ == "__main__":
    main()
