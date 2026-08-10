"""Worked example: how long a vacuum chamber takes to pump down, and the pump's gas load.

A 100 L chamber is evacuated from atmosphere (1000 mbar) to 1 mbar by a pump rated at 10 L/s. How
long does the ideal pump-down take, and what throughput is the pump moving once it reaches 1 mbar?

The pump-down time is t = (V/S)·ln(P₁/P₂) = (100/10)·ln(1000/1) ≈ 69 s — and because the pressure
falls exponentially, each further decade costs the same ~23 s, which is why the last few decades to
high vacuum take patience. At the 1 mbar operating point the throughput is Q = S·P = 10 L/s × 1 mbar
= 10 mbar·L/s; to hold that pressure against a leak, the leak rate must stay below this.

(This ignores outgassing and leaks, which set the real high-vacuum floor.)

Run it directly (``python examples/vacuum_chamber_pump_down.py``);
:func:`chamber_pump_down` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import vacuum_pump_down_time, vacuum_throughput
from anvilate.units import Quantity

CHAMBER_VOLUME = Quantity.parse("100 L")
PUMPING_SPEED = Quantity.parse("10 L/s")
INITIAL_PRESSURE = Quantity.parse("1000 mbar")
FINAL_PRESSURE = Quantity.parse("1 mbar")


def chamber_pump_down() -> dict[str, float]:
    """Return the pump-down time (s) and the throughput (mbar·L/s) at the final pressure."""
    t = vacuum_pump_down_time(
        chamber_volume=CHAMBER_VOLUME,
        pumping_speed=PUMPING_SPEED,
        initial_pressure=INITIAL_PRESSURE,
        final_pressure=FINAL_PRESSURE,
    )
    q = vacuum_throughput(pumping_speed=PUMPING_SPEED, pressure=FINAL_PRESSURE)
    return {
        "pump_down_time_s": t.to("s").magnitude,
        "throughput_mbar_l_per_s": q.to("mbar*L/s").magnitude,
    }


def main() -> None:
    d = chamber_pump_down()
    print("100 L chamber, 10 L/s pump, 1000 mbar -> 1 mbar:")
    print(f"  pump-down time        : {d['pump_down_time_s']:.0f} s")
    print(f"  throughput at 1 mbar  : {d['throughput_mbar_l_per_s']:.1f} mbar*L/s")


if __name__ == "__main__":
    main()
