"""Worked example: the wave relation v = f·λ across three kinds of wave.

Every travelling wave links its speed, frequency, and wavelength through v = f·λ, and which one you
solve for depends on what you know. This example runs the relation three ways — a sound wave, an FM
radio wave, and a light wave — each highlighting a different unknown.

A 440 Hz concert-A tone with a 0.78 m wavelength travels at about 343 m/s, the speed of sound in
air. A 100 MHz FM radio wave, travelling at the speed of light, has a 3 m wavelength — which is why
FM antennas are about that size. And green light of 500 nm wavelength, also at light speed, works
out to a frequency of about 6.0e14 Hz. This example reports the sound-wave speed, the FM wavelength,
and the
green-light frequency.

Run it directly (``python examples/wave_relation.py``);
:func:`wave_quantities` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    frequency_from_wavelength,
    wave_speed,
    wavelength_from_frequency,
)
from anvilate.units import Quantity

SPEED_OF_LIGHT = Quantity(magnitude=299792458.0, unit="m/s")


def wave_quantities() -> dict[str, float]:
    """Return the sound-wave speed, the FM wavelength, and the green-light frequency."""
    sound_speed = wave_speed(
        frequency=Quantity(magnitude=440.0, unit="Hz"),
        wavelength=Quantity(magnitude=0.78, unit="m"),
    )
    fm_wavelength = wavelength_from_frequency(
        frequency=Quantity(magnitude=100e6, unit="Hz"), wave_speed=SPEED_OF_LIGHT
    )
    light_frequency = frequency_from_wavelength(
        wavelength=Quantity(magnitude=500e-9, unit="m"), wave_speed=SPEED_OF_LIGHT
    )
    return {
        "sound_speed_m_s": sound_speed.to("m/s").magnitude,
        "fm_wavelength_m": fm_wavelength.to("m").magnitude,
        "green_light_frequency_thz": light_frequency.to("Hz").magnitude / 1e12,
    }


def main() -> None:
    d = wave_quantities()
    print(f"sound-wave speed (440 Hz, 0.78 m): {d['sound_speed_m_s']:.0f} m/s")
    print(f"FM wavelength (100 MHz): {d['fm_wavelength_m']:.2f} m")
    print(f"green-light frequency (500 nm): {d['green_light_frequency_thz']:.0f} THz")


if __name__ == "__main__":
    main()
