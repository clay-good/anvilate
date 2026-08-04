"""Worked example: a machine's rated sound power vs what the operator hears, and why corners hurt.

A machine's nameplate gives its sound *power* level L_w — a fixed property of the source — but the
sound *pressure* level L_p an operator is exposed to depends on distance and, critically, on where
the machine sits. Each nearby reflecting surface doubles the directivity factor Q and adds 3 dB:
Q = 1 out in the open, 2 on a floor, 4 against a wall, 8 in a corner. This example takes a 95 dB(A)
machine and an operator 2 m away, and computes the pressure level for the same machine placed three
ways. Out in the open it is about 78 dB(A); pushed into a corner, the three reflecting surfaces add
9 dB onto it, to 87 dB(A) — over the hearing-conservation action level, from nothing but where the
machine was set down. It is the cheapest noise control there is: move the machine away from the
corner before reaching for enclosures.

Run it directly (``python examples/machine_noise_placement.py``);
:func:`operator_levels` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import sound_pressure_from_power_level
from anvilate.units import Quantity

SOUND_POWER_LEVEL = 95.0  # dB(A) nameplate
OPERATOR_DISTANCE = Quantity.parse("2 m")


def operator_levels() -> dict[str, float]:
    """Return the operator sound pressure level for free-field, on-floor, and corner placement."""
    return {
        "free_field_q1": sound_pressure_from_power_level(
            sound_power_level=SOUND_POWER_LEVEL, distance=OPERATOR_DISTANCE, directivity_factor=1.0
        ),
        "on_floor_q2": sound_pressure_from_power_level(
            sound_power_level=SOUND_POWER_LEVEL, distance=OPERATOR_DISTANCE, directivity_factor=2.0
        ),
        "in_corner_q8": sound_pressure_from_power_level(
            sound_power_level=SOUND_POWER_LEVEL, distance=OPERATOR_DISTANCE, directivity_factor=8.0
        ),
    }


def main() -> None:
    lv = operator_levels()
    print(f"free field (open)   : {lv['free_field_q1']:.0f} dB(A) at the operator")
    print(f"on a floor          : {lv['on_floor_q2']:.0f} dB(A)")
    print(f"in a corner         : {lv['in_corner_q8']:.0f} dB(A) (+9 dB from reflections alone)")
    print(
        "  -> the same machine is 9 dB louder in a corner; placement is the cheapest noise control"
    )


if __name__ == "__main__":
    main()
