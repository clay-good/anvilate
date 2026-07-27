"""Worked example: the servo that clears every instant and still overheats.

A pick-and-place axis runs a hard repeating cycle: 2 N·m to accelerate for 0.2 s,
2 N·m to brake for 0.2 s, then a 0.6 s dwell while the gripper works. The motor's
peak rating of 3 N·m covers the hardest instant with room to spare (SF 1.50), and
nothing in the cycle ever demands more. Sized on instants, the motor looks fine.

But winding heat goes as torque *squared*, integrated over the whole cycle -- the
screen for it is the RMS torque √(ΣT²·t/Σt), compared against the motor's 1.2 N·m
*continuous* rating. Over this 1.0 s cycle the RMS works out to 1.26 N·m (0.95):
the motor fails thermally at a cycle it passes instant-by-instant, and it will cook
its windings a few hundred cycles in, with no single moment ever looking wrong.

The fix costs throughput, not torque: stretching the dwell to 1.0 s -- the same
moves, the same peaks, just more cooling time in the denominator -- drops the RMS to
1.07 N·m (1.12). The lesson is that a servo is sized twice, peak *and* RMS, and the
second gate is the one fast cycles fail: the dwell is not dead time but thermal
recovery, and cycle rate is a thermal variable. When the RMS misses narrowly, slow
the cycle or shrink the move torque; the peak rating was never the problem.

Run it directly (``python examples/servo_duty_cycle_thermal.py``);
:func:`screen_fast_cycle` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import rms_torque_over_cycle
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

ACCEL_TORQUE = Quantity.parse("2 N*m")
ACCEL_TIME = Quantity.parse("0.2 s")
BRAKE_TIME = Quantity.parse("0.2 s")
MOTOR_PEAK_TORQUE = Quantity.parse("3 N*m")
MOTOR_CONTINUOUS_TORQUE = Quantity.parse("1.2 N*m")

FAST_DWELL = Quantity.parse("0.6 s")  # a 1.0 s cycle
RELAXED_DWELL = Quantity.parse("1.0 s")  # a 1.4 s cycle


def _screen(dwell: Quantity) -> Scorecard:
    rms = rms_torque_over_cycle(
        torques=[ACCEL_TORQUE, ACCEL_TORQUE, Quantity.parse("0 N*m")],
        durations=[ACCEL_TIME, BRAKE_TIME, dwell],
    )
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "peak rating vs hardest instant",
                computed=MOTOR_PEAK_TORQUE.to("N*m").magnitude / ACCEL_TORQUE.to("N*m").magnitude,
                required=1.0,
            ),
            ScorecardEntry.from_safety_factor(
                "continuous rating vs cycle RMS torque",
                computed=MOTOR_CONTINUOUS_TORQUE.to("N*m").magnitude / rms.to("N*m").magnitude,
                required=1.0,
            ),
        )
    )


def screen_fast_cycle() -> Scorecard:
    """Screen the 1.0 s cycle: every instant passes, the thermal RMS does not."""
    return _screen(FAST_DWELL)


def screen_relaxed_cycle() -> Scorecard:
    """Screen the 1.4 s cycle: the longer dwell cools the same moves."""
    return _screen(RELAXED_DWELL)


def main() -> None:
    for label, dwell in (("fast (0.6 s dwell)", FAST_DWELL), ("relaxed (1.0 s)", RELAXED_DWELL)):
        rms = rms_torque_over_cycle(
            torques=[ACCEL_TORQUE, ACCEL_TORQUE, Quantity.parse("0 N*m")],
            durations=[ACCEL_TIME, BRAKE_TIME, dwell],
        )
        print(f"{label}: RMS torque {rms.to('N*m').magnitude:.2f} N*m")
    print("\nfast cycle:")
    print(screen_fast_cycle())
    print("\nrelaxed cycle:")
    print(screen_relaxed_cycle())


if __name__ == "__main__":
    main()
