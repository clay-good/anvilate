"""Worked example: the detection range of an X-band surveillance radar.

A radar's reach is set by its power budget: how much power it transmits, how tightly its antenna
focuses, and how faint an echo its receiver can still detect. The radar range equation ties these
together, and its fourth-power dependence on range is what makes long reach so expensive.

An X-band radar (wavelength 0.03 m, 10 GHz) transmits 1 MW through an antenna of gain 1,000 (30 dBi)
and can detect echoes down to 1e-13 W. Against a 1 m^2 target it reaches about 46 km. At that range
the returning echo power is just at the 1e-13 W detection floor, confirming the budget closes. Its
pulse repetition frequency of 1 kHz sets a maximum unambiguous range of about 150 km, comfortably
beyond the detection range. This example reports the detection range, the echo power at that range,
and the maximum unambiguous range.

Run it directly (``python examples/radar_range_budget.py``);
:func:`radar_range_budget` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    max_unambiguous_range,
    radar_max_range,
    radar_received_power,
)
from anvilate.units import Quantity

TRANSMIT_POWER = Quantity(magnitude=1e6, unit="W")
ANTENNA_GAIN = 1000.0  # linear (30 dBi)
WAVELENGTH = Quantity(magnitude=0.03, unit="m")  # X-band, 10 GHz
TARGET_CROSS_SECTION = Quantity(magnitude=1.0, unit="m**2")
MIN_DETECTABLE_POWER = Quantity(magnitude=1e-13, unit="W")
PRF = Quantity(magnitude=1000.0, unit="Hz")


def radar_range_budget() -> dict[str, float]:
    """Return the detection range, the echo power at that range, and the unambiguous range."""
    r_max = radar_max_range(
        transmit_power=TRANSMIT_POWER,
        antenna_gain=ANTENNA_GAIN,
        wavelength=WAVELENGTH,
        target_cross_section=TARGET_CROSS_SECTION,
        min_detectable_power=MIN_DETECTABLE_POWER,
    )
    echo = radar_received_power(
        transmit_power=TRANSMIT_POWER,
        antenna_gain=ANTENNA_GAIN,
        wavelength=WAVELENGTH,
        target_cross_section=TARGET_CROSS_SECTION,
        target_range=r_max,
    )
    r_unambiguous = max_unambiguous_range(pulse_repetition_frequency=PRF)
    return {
        "detection_range_km": r_max.to("m").magnitude / 1000.0,
        "echo_power_at_rmax_w": echo.to("W").magnitude,
        "unambiguous_range_km": r_unambiguous.to("m").magnitude / 1000.0,
    }


def main() -> None:
    d = radar_range_budget()
    print(f"detection range: {d['detection_range_km']:.1f} km")
    print(f"echo power at detection range: {d['echo_power_at_rmax_w']:.2e} W")
    print(f"maximum unambiguous range: {d['unambiguous_range_km']:.1f} km")


if __name__ == "__main__":
    main()
