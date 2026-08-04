"""Worked example: adding up machinery noise, and why quieting one machine barely helps.

A worker standing among several machines hears them all at once, but decibels don't add the way
intuition expects — they combine by energy, so the loudest source dominates and the quiet ones
barely register. This example puts an operator near four machines (a 92 dB compressor down to an
80 dB fan) and finds the combined level: it lands just above the loudest source, because everything
more than a few decibels quieter is almost inaudible against it. That has a blunt design
consequence — silencing the 80 dB fan does essentially nothing, while taming the 92 dB compressor is
the only move that matters. The example then uses the inverse-square law to find how far back the
worker would have to stand for the noise to fall below the 85 dB action level, the distance a
hearing-conservation layout has to buy.

Run it directly (``python examples/plant_noise_exposure.py``);
:func:`noise_assessment` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import inverse_square_attenuation, sound_level_sum
from anvilate.units import Quantity

MACHINE_LEVELS = [92.0, 88.0, 85.0, 80.0]  # dB at the operator's 1 m position
MEASUREMENT_DISTANCE = Quantity.parse("1 m")
ACTION_LEVEL = 85.0  # dB, the hearing-conservation action level


def noise_assessment() -> dict[str, float]:
    """Return the combined level (dB), the margin over the loudest, and the safe distance (m)."""
    combined = sound_level_sum(levels=MACHINE_LEVELS)
    loudest = max(MACHINE_LEVELS)
    # Distance at which the inverse-square law drops the combined level to the action level:
    # combined - 20*log10(r/1) = 85  ->  r = 10^((combined-85)/20).
    safe_distance = 10.0 ** ((combined - ACTION_LEVEL) / 20.0)
    # Confirm with the attenuation function.
    at_safe = inverse_square_attenuation(
        reference_level=combined,
        reference_distance=MEASUREMENT_DISTANCE,
        distance=Quantity(magnitude=safe_distance, unit="m"),
    )
    return {
        "combined_db": combined,
        "loudest_db": loudest,
        "margin_over_loudest": combined - loudest,
        "safe_distance_m": safe_distance,
        "level_at_safe_distance": at_safe,
    }


def main() -> None:
    a = noise_assessment()
    print(f"four machines combine to : {a['combined_db']:.1f} dB")
    print(f"  only {a['margin_over_loudest']:.1f} dB above the loudest ({a['loudest_db']:.0f} dB)")
    print(f"drops below {ACTION_LEVEL:.0f} dB action level at {a['safe_distance_m']:.1f} m")
    print("  -> silence the loudest machine, not the quiet ones; energy-summing hides the rest")


if __name__ == "__main__":
    main()
