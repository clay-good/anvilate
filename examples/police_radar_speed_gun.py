"""Worked example: a police speed gun and its velocity-aliasing limit.

A Doppler radar reads speed from the frequency shift of the echo it gets back from a moving target.
Because the wave makes a round trip, that shift is twice the one-way case, and inverting it gives
the target's speed. A pulsed radar has a second concern: it samples the echo at its pulse repetition
frequency, so beyond a maximum unambiguous velocity a fast target aliases to a wrong reading. This
example works both for an X-band traffic radar.

The gun transmits at 10.5 GHz. A car closing at 30 m/s (about 67 mph) returns an echo shifted by
about 2101 Hz, and reading that shift back recovers the 30 m/s — the number on the display. With a
5 kHz pulse repetition frequency, the radar measures unambiguously up to about 35.7 m/s (80 mph);
a faster vehicle folds to a lower apparent speed unless the PRF is raised. The example reports
the Doppler shift, the speed recovered from it, and the maximum unambiguous speed.

Run it directly (``python examples/police_radar_speed_gun.py``);
:func:`speed_gun` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    max_unambiguous_velocity,
    radar_doppler_shift,
    radial_velocity_from_doppler,
)
from anvilate.units import Quantity

TRANSMIT_FREQUENCY = Quantity(magnitude=10.5e9, unit="Hz")
TARGET_SPEED = Quantity.parse("30 m/s")
PULSE_REPETITION_FREQUENCY = Quantity(magnitude=5000.0, unit="Hz")


def speed_gun() -> dict[str, float]:
    """Return the Doppler shift, the speed recovered from it, and the max unambiguous speed."""
    shift = radar_doppler_shift(transmit_frequency=TRANSMIT_FREQUENCY, radial_velocity=TARGET_SPEED)
    speed = radial_velocity_from_doppler(transmit_frequency=TRANSMIT_FREQUENCY, doppler_shift=shift)
    v_max = max_unambiguous_velocity(
        transmit_frequency=TRANSMIT_FREQUENCY,
        pulse_repetition_frequency=PULSE_REPETITION_FREQUENCY,
    )
    return {
        "doppler_shift_hz": shift.to("Hz").magnitude,
        "recovered_speed_m_s": speed.to("m/s").magnitude,
        "max_unambiguous_speed_m_s": v_max.to("m/s").magnitude,
    }


def main() -> None:
    d = speed_gun()
    print(f"Doppler shift at 30 m/s: {d['doppler_shift_hz']:.0f} Hz")
    print(f"speed recovered from the shift: {d['recovered_speed_m_s']:.0f} m/s")
    print(f"max unambiguous speed (5 kHz PRF): {d['max_unambiguous_speed_m_s']:.1f} m/s")


if __name__ == "__main__":
    main()
