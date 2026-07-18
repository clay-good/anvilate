"""Worked example: the three-stage reducer that missed on paper losses.

A conveyor gearbox reduces a 3 kW motor at 1500 rpm through three gear stages to
drive a drum that needs 650 N*m. The reduction is generous — 20/60, 20/60, and
20/80 tooth pairs multiply to 36:1 — so the ideal output torque is
19.1 N*m * 36 = 688 N*m, a comfortable 1.06 margin. On paper, done.

But every mesh loses a little, and the losses compound. Three 97%-efficient
stages do not keep 97%; they keep 0.97^3 = 91.3%. That drops the real output
torque to 628 N*m, and the drum demand it cleared by 6% on paper it now misses
by 3% (0.97 margin). Nothing about the gearing changed — only the honesty of the
torque budget did.

A drivetrain must be sized on delivered torque, not ideal torque, and the gap is
exactly the train efficiency. The per-mesh efficiencies are manufacturer's data,
declared inline like any allowable; a worm stage would make the gap far larger.

Run it directly (``python examples/multistage_reducer_efficiency.py``);
:func:`screen_reducer` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import gear_train_efficiency, gear_train_value, torque_from_power
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

MOTOR_POWER = Quantity.parse("3 kW")
MOTOR_SPEED = Quantity.parse("1500 rpm")
DRUM_TORQUE_DEMAND = Quantity.parse("650 N*m")

DRIVER_TEETH = [20, 20, 20]
DRIVEN_TEETH = [60, 60, 80]
MESH_EFFICIENCIES = [0.97, 0.97, 0.97]


def output_torques() -> tuple[float, float]:
    """The ideal and real (loss-adjusted) output torques in N*m."""
    input_torque = torque_from_power(power=MOTOR_POWER, rotational_speed=MOTOR_SPEED)
    ratio = abs(1.0 / gear_train_value(driver_teeth=DRIVER_TEETH, driven_teeth=DRIVEN_TEETH))
    efficiency = gear_train_efficiency(mesh_efficiencies=MESH_EFFICIENCIES)
    ideal = input_torque.to("N*m").magnitude * ratio
    return ideal, ideal * efficiency


def screen_reducer() -> Scorecard:
    """Screen the output torque against the drum demand, ideal vs real."""
    demand = DRUM_TORQUE_DEMAND.to("N*m").magnitude
    ideal, real = output_torques()
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor(
                "ideal (lossless) output torque", computed=ideal / demand, required=1.0
            ),
            ScorecardEntry.from_safety_factor(
                "real output torque (three-stage losses)", computed=real / demand, required=1.0
            ),
        )
    )


def main() -> None:
    ideal, real = output_torques()
    print(f"ideal {ideal:.0f} N*m, real {real:.0f} N*m (train efficiency {real / ideal:.1%})")
    print(screen_reducer())


if __name__ == "__main__":
    main()
