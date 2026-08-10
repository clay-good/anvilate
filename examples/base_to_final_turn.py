"""Worked example: the base-to-final overshoot that stalls the wing.

A light single is turning from base to final in the traffic pattern at 70 knots, comfortably above
its 50-knot wings-level stall. The pilot rolls into a steep 60-degree bank to tighten the turn and
salvage an overshot centreline. That bank drives the load factor to n = 1/cos 60 deg = 2.0 g, and a
wing pulling 2 g stalls at V_s.√n = 50.√2 = 70.7 knots -- *above* the 70 knots being flown. The
required 1.3.V_s approach margin is nowhere in sight; the inner wing stalls, the aircraft rolls into
the ground. This is the classic stall-spin accident, and the numbers show it is geometry, not bad
luck: the accelerated stall speed climbs with the square root of load factor, and load factor climbs
with the secant of bank.

The fix is not more airspeed but *less bank*. Held to a 30-degree bank the load factor is only
n = 1.15 g, the accelerated stall speed falls to 50.√1.15 = 53.7 knots, and 70 knots now clears it
with a 1.30 margin -- exactly the 1.3.V_s the approach wants. The turn is wider and takes longer, but
a wide turn flown is better than a tight one stalled.

The lesson is that bank angle, not airspeed, is the lever in a low-speed turn: every degree of bank
raises the speed at which the wing quits, so an overshoot is corrected by going around, never by
tightening the turn.

Run it directly (``python examples/base_to_final_turn.py``);
:func:`screen_base_to_final_turn` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import accelerated_stall_speed, load_factor_from_bank_angle
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

WINGS_LEVEL_STALL_SPEED = Quantity.parse("50 knot")
APPROACH_SPEED = Quantity.parse("70 knot")
STEEP_BANK = 60.0  # degrees -- the overshoot-salvaging bank
SHALLOW_BANK = 30.0  # degrees -- the disciplined pattern bank
APPROACH_STALL_MARGIN = 1.30  # standard 1.3.V_s approach margin


def _screen(bank_angle: float) -> Scorecard:
    load_factor = load_factor_from_bank_angle(bank_angle=bank_angle)
    stall_speed = accelerated_stall_speed(
        level_stall_speed=WINGS_LEVEL_STALL_SPEED, load_factor=load_factor
    )
    margin = APPROACH_SPEED.to("m/s").magnitude / stall_speed.to("m/s").magnitude
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "approach speed vs accelerated stall",
                computed=margin,
                required=APPROACH_STALL_MARGIN,
            ),
        )
    )


def screen_base_to_final_turn() -> Scorecard:
    """Screen the steep 60-degree base-to-final turn: it stalls the wing above pattern speed."""
    return _screen(STEEP_BANK)


def screen_disciplined_turn() -> Scorecard:
    """Screen the shallow 30-degree turn: the same speed now clears the accelerated stall."""
    return _screen(SHALLOW_BANK)


def main() -> None:
    print("steep 60-degree bank:")
    print(screen_base_to_final_turn())
    print("\ndisciplined 30-degree bank:")
    print(screen_disciplined_turn())


if __name__ == "__main__":
    main()
