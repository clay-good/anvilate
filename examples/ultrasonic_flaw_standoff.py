"""Worked example: the ultrasonic probe that cannot resolve a flaw in its near field.

An inspector needs to size a suspected flaw 15 mm deep in a steel forging (sound speed 5900 m/s). The
first probe reached for is a 10 mm, 5 MHz element. Its near-field length -- the chaotic zone where the
on-axis beam pressure swings through maxima and minima -- is N = D^2*f/(4*c) = 21.2 mm. The flaw at
15 mm sits *inside* that near field, so its echo amplitude is unreliable and any size read off it is
suspect: a safety factor of 0.71 on flaw-depth-over-near-field, under one, which is the signal the
inspection is unsound before it starts.

Swapping to a smaller 6 mm element (same 5 MHz) shrinks the near field, because N grows with the
square of the diameter: N falls to 7.6 mm, so the 15 mm flaw now lies well into the clean far field --
a safety factor of 1.97 -- where its echo can be trusted and sized. The trade is a wider, less
directional beam, but the flaw is now in the part of the field the detector can actually measure.

The lesson is that a flaw must be beyond the probe's near field to be sized reliably: check
d > D^2*f/(4*c) for the depth of interest, and if it is not, drop to a smaller-diameter (or
lower-frequency) probe to pull the near field in ahead of the target.

Run it directly (``python examples/ultrasonic_flaw_standoff.py``);
:func:`screen_large_probe` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import near_field_length
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

FLAW_DEPTH = Quantity.parse("15 mm")
FREQUENCY = Quantity.parse("5 MHz")
STEEL_SOUND_SPEED = Quantity.parse("5900 m/s")
LARGE_PROBE_DIAMETER = Quantity.parse("10 mm")
SMALL_PROBE_DIAMETER = Quantity.parse("6 mm")


def _screen(transducer_diameter: Quantity) -> Scorecard:
    near_field = near_field_length(
        transducer_diameter=transducer_diameter,
        frequency=FREQUENCY,
        sound_speed=STEEL_SOUND_SPEED,
    )
    margin = FLAW_DEPTH.to("mm").magnitude / near_field.to("mm").magnitude
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "flaw depth vs near-field length",
                computed=margin,
                required=1.0,
            ),
        )
    )


def screen_large_probe() -> Scorecard:
    """Screen the 10 mm probe: its deep near field swallows the 15 mm flaw."""
    return _screen(LARGE_PROBE_DIAMETER)


def screen_small_probe() -> Scorecard:
    """Screen the 6 mm probe: the shorter near field leaves the flaw in the clean far field."""
    return _screen(SMALL_PROBE_DIAMETER)


def main() -> None:
    print("10 mm probe:")
    print(screen_large_probe())
    print("\n6 mm probe:")
    print(screen_small_probe())


if __name__ == "__main__":
    main()
