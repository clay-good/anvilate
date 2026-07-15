"""Worked example: two discs that each passed, together resonate.

A lineshaft runs at 1500 rpm (25 Hz) and carries two pulleys. Checked one at a
time, each is fine: the shaft's lateral natural frequency with only pulley A
aboard is about 42 Hz, and with only pulley B about 39 Hz — both comfortably
above a 1.25x running-speed resonance floor of 31 Hz. But the two masses do not
each get their own shaft; they share one, and flexibilities add. Dunkerley's
method combines them as 1/f^2 = 1/f_A^2 + 1/f_B^2, dropping the real first
critical speed to about 29 Hz — below the floor and only 1.15x the running
speed. Screening the pulleys individually hides the resonance; the shaft has one
fundamental, not two, and it sits lower than either mass would suggest.

Run it directly (``python examples/lineshaft_critical_speed.py``);
:func:`screen_lineshaft` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    dunkerley_fundamental_frequency,
    frequency_scorecard,
    natural_frequency_from_deflection,
)
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

RUNNING_SPEED = Quantity.parse("25 Hz")  # 1500 rpm
RESONANCE_MARGIN = 1.25  # keep the critical speed >= 1.25x running
# Static shaft deflection under each pulley's weight alone (from the bearing span).
DEFLECTION_A = Quantity.parse("0.14 mm")
DEFLECTION_B = Quantity.parse("0.16 mm")


def screen_lineshaft() -> Scorecard:
    """Screen each pulley's stand-alone critical speed and the Dunkerley-combined
    one against a resonance floor set above the running speed."""
    f_a = natural_frequency_from_deflection(DEFLECTION_A)
    f_b = natural_frequency_from_deflection(DEFLECTION_B)
    f_combined = dunkerley_fundamental_frequency([f_a, f_b])
    floor = Quantity(magnitude=RESONANCE_MARGIN * RUNNING_SPEED.to("Hz").magnitude, unit="Hz")
    return Scorecard(
        entries=(
            frequency_scorecard("pulley A alone", frequency=f_a, min_frequency=floor),
            frequency_scorecard("pulley B alone", frequency=f_b, min_frequency=floor),
            frequency_scorecard("both (Dunkerley)", frequency=f_combined, min_frequency=floor),
        )
    )


def main() -> None:
    card = screen_lineshaft()
    for entry in card.entries:
        print(entry)
    print(card)


if __name__ == "__main__":
    main()
