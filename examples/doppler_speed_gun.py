"""Worked example: reading a source's speed from its pitch shift, and the sonic-boom cone.

When a sound source moves, the pitch a listener hears is not the pitch emitted: approaching, the
waves bunch up and the pitch rises; receding, they stretch and it falls. The size of that shift
encodes the speed, which is how a Doppler speed gun, a sonar, or an acoustic tachometer measures how
fast something moves — emit a known frequency, measure the returned one, and invert the Doppler
relation. Push the source past the speed of sound and the picture changes entirely: the waves cannot
run ahead, and pile onto a cone that trails behind as the shock we hear as a sonic boom.

This example emits a 1000 Hz tone from a source approaching a stationary listener at 30 m/s, with
sound at 343 m/s. The listener hears it shifted up to about 1096 Hz. Run the measurement backward —
given the emitted 1000 Hz and the measured 1096 Hz — and the Doppler inverse recovers the closing
speed of 30 m/s, the trick behind every speed gun. Finally, for a source flying at Mach 2, the Mach
cone half-angle works out to 30 degrees — the angle of the shock cone trailing a supersonic object.
The example reports the shifted frequency, the speed recovered from it, and the Mach cone angle, so
both faces of moving-source acoustics are explicit.

Run it directly (``python examples/doppler_speed_gun.py``);
:func:`moving_source` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    doppler_shifted_frequency,
    doppler_velocity_from_shift,
    mach_cone_angle,
)
from anvilate.units import Quantity

SOURCE_FREQUENCY = Quantity.parse("1000 Hz")
SPEED_OF_SOUND = Quantity.parse("343 m/s")
SOURCE_SPEED = Quantity.parse("30 m/s")
STATIONARY = Quantity.parse("0 m/s")
SUPERSONIC_MACH = 2.0


def moving_source() -> dict[str, float]:
    """Return the Doppler-shifted frequency, the speed recovered from it, and the cone angle."""
    shifted = doppler_shifted_frequency(
        source_frequency=SOURCE_FREQUENCY,
        speed_of_sound=SPEED_OF_SOUND,
        source_velocity=SOURCE_SPEED,
        observer_velocity=STATIONARY,
    )
    recovered_speed = doppler_velocity_from_shift(
        source_frequency=SOURCE_FREQUENCY,
        observed_frequency=shifted,
        speed_of_sound=SPEED_OF_SOUND,
    )
    cone = mach_cone_angle(mach_number=SUPERSONIC_MACH)
    return {
        "shifted_frequency_hz": shifted.to("Hz").magnitude,
        "recovered_speed_m_s": recovered_speed.to("m/s").magnitude,
        "mach_cone_angle_deg": cone,
    }


def main() -> None:
    d = moving_source()
    print(f"emitted 1000 Hz heard as: {d['shifted_frequency_hz']:.0f} Hz (approaching)")
    print(f"speed recovered from the shift: {d['recovered_speed_m_s']:.0f} m/s (matches 30 m/s)")
    print(f"Mach cone half-angle at Mach 2: {d['mach_cone_angle_deg']:.0f} deg")


if __name__ == "__main__":
    main()
