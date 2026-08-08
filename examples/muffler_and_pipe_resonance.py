"""Worked example: the frequencies that ring — a Helmholtz muffler and open vs closed pipes.

Air trapped in a cavity or a tube has natural frequencies at which it resonates, and knowing them is
the difference between silencing a noise and amplifying it. A Helmholtz resonator — a volume of air
behind a narrow neck — rings at a single low frequency set by the neck and cavity geometry; it is
the tuned element inside an exhaust muffler or a cavity absorber, sized to swallow one bad tone. A
straight pipe resonates instead at a harmonic series, and whether its far end is open or closed
changes that series completely: an open pipe sounds all harmonics, a closed pipe only the odd ones
and an octave lower for the same length.

This example works at room temperature, where sound travels at 343 m/s. A Helmholtz resonator with a
5 cm² neck, 2 cm long, on a 1-litre cavity rings at about 273 Hz — the tone that a muffler of these
dimensions is built to absorb. A 1 m pipe open at both ends has its fundamental at about 172 Hz and
a full harmonic series above it (344 Hz, 515 Hz, …). Close one end and the same 1 m pipe drops to a
fundamental of about 86 Hz — an octave lower — and rings only on odd harmonics (86, 257, 429 Hz).
The example reports the Helmholtz frequency and the first two modes of each pipe, so the contrast
between cavity and pipe resonance, and between open and closed pipes, is explicit.

Run it directly (``python examples/muffler_and_pipe_resonance.py``);
:func:`resonances` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    closed_pipe_resonance_frequency,
    helmholtz_resonator_frequency,
    open_pipe_resonance_frequency,
)
from anvilate.units import Quantity

SPEED_OF_SOUND = Quantity.parse("343 m/s")  # air at ~20 C
NECK_AREA = Quantity.parse("5 cm**2")
NECK_LENGTH = Quantity.parse("2 cm")
CAVITY_VOLUME = Quantity.parse("1 L")
PIPE_LENGTH = Quantity.parse("1 m")


def resonances() -> dict[str, float]:
    """Return the Helmholtz frequency and the first two modes of an open and a closed pipe."""
    helmholtz = helmholtz_resonator_frequency(
        speed_of_sound=SPEED_OF_SOUND,
        neck_area=NECK_AREA,
        cavity_volume=CAVITY_VOLUME,
        neck_length=NECK_LENGTH,
    )
    open_1 = open_pipe_resonance_frequency(speed_of_sound=SPEED_OF_SOUND, pipe_length=PIPE_LENGTH)
    open_2 = open_pipe_resonance_frequency(
        speed_of_sound=SPEED_OF_SOUND, pipe_length=PIPE_LENGTH, mode=2
    )
    closed_1 = closed_pipe_resonance_frequency(
        speed_of_sound=SPEED_OF_SOUND, pipe_length=PIPE_LENGTH
    )
    closed_2 = closed_pipe_resonance_frequency(
        speed_of_sound=SPEED_OF_SOUND, pipe_length=PIPE_LENGTH, mode=2
    )
    return {
        "helmholtz_hz": helmholtz.to("Hz").magnitude,
        "open_pipe_fundamental_hz": open_1.to("Hz").magnitude,
        "open_pipe_second_hz": open_2.to("Hz").magnitude,
        "closed_pipe_fundamental_hz": closed_1.to("Hz").magnitude,
        "closed_pipe_second_hz": closed_2.to("Hz").magnitude,
    }


def main() -> None:
    d = resonances()
    print(f"Helmholtz resonator: {d['helmholtz_hz']:.0f} Hz (muffler tuning)")
    print(
        f"open pipe (1 m): {d['open_pipe_fundamental_hz']:.0f} Hz, "
        f"then {d['open_pipe_second_hz']:.0f} Hz (all harmonics)"
    )
    print(
        f"closed pipe (1 m): {d['closed_pipe_fundamental_hz']:.0f} Hz, "
        f"then {d['closed_pipe_second_hz']:.0f} Hz (odd harmonics, octave lower)"
    )


if __name__ == "__main__":
    main()
