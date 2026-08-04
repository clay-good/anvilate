"""Worked example: why slamming a valve can burst a pipe the working pressure never troubles.

A pipeline sits at a comfortable working pressure, sized with a healthy margin — and then someone
closes a valve too fast and it fails anyway. The culprit is water hammer: stopping a moving column
of water abruptly turns its momentum into a pressure wave that races back up the line, and the
Joukowsky equation says that surge is enormous. This example takes water flowing at 2.5 m/s in a
500 m steel line at an 800 kPa working pressure and shows the surge from an instant valve closure
is several megapascals — many times the working pressure, well past what the pipe is rated for.
It also gives the critical closure time: close the valve slower than the wave's round-trip and the
surge eases off, which is the whole reason large valves are geared to close slowly. The steady
pressure was never the danger; the transient is.

Run it directly (``python examples/water_hammer_valve_closure.py``);
:func:`surge_check` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import joukowsky_surge_pressure, surge_wave_period
from anvilate.units import Quantity

DENSITY = Quantity.parse("1000 kg/m**3")
WAVE_SPEED = Quantity.parse("1200 m/s")  # water in steel pipe
FLOW_VELOCITY = Quantity.parse("2.5 m/s")  # stopped to zero on closure
PIPE_LENGTH = Quantity.parse("500 m")
WORKING_PRESSURE = Quantity.parse("800 kPa")


def surge_check() -> dict[str, float]:
    """Return the surge pressure (kPa), its ratio to working pressure, and the critical time (s)."""
    surge = (
        joukowsky_surge_pressure(
            density=DENSITY, wave_speed=WAVE_SPEED, velocity_change=FLOW_VELOCITY
        )
        .to("kPa")
        .magnitude
    )
    critical_time = (
        surge_wave_period(pipe_length=PIPE_LENGTH, wave_speed=WAVE_SPEED).to("s").magnitude
    )
    return {
        "surge_kpa": surge,
        "surge_over_working": surge / WORKING_PRESSURE.to("kPa").magnitude,
        "critical_closure_s": critical_time,
    }


def main() -> None:
    s = surge_check()
    surge_mpa = s["surge_kpa"] / 1000.0
    print(f"working pressure : {WORKING_PRESSURE.to('kPa').magnitude:.0f} kPa")
    print(f"water-hammer surge : {surge_mpa:.1f} MPa ({s['surge_over_working']:.0f}x working)")
    print(f"critical closure : {s['critical_closure_s']:.2f} s — close slower than this to ease it")
    print("  -> the steady pressure is fine; the transient from a fast closure is what bursts it")


if __name__ == "__main__":
    main()
