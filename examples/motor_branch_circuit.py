"""Worked example: sizing a motor branch circuit for the current it really draws.

A motor's nameplate gives its mechanical output, but the wire feeding it carries the electrical
input — the output plus the motor's own losses — and then the code adds a margin on top for
continuous running. Getting either step wrong undersizes the conductor. This example works both for
a 15 kW three-phase motor at 400 V, power factor 0.85, efficiency 0.90.

First, the full-load current is the input over the losses: 15 kW of shaft power needs about 16.7 kW
of electrical input, and at 400 V and 0.85 power factor that is 28.3 A — noticeably more than the
25.5 A you would get by treating the nameplate 15 kW as if it were the electrical draw. Then the NEC
sizes the branch-circuit conductors for 125% of the full-load current, because a motor runs
continuously and pulls a surge every time it starts: 1.25 × 28.3 = 35.4 A. A conductor for the
naive 25.5 A would be two steps too small once the efficiency and the 125% factor are both applied.
The lesson is that a motor circuit is sized off neither the nameplate kW nor the running current
alone: the efficiency turns output into input, and the code factor turns running current into
conductor ampacity.

Run it directly (``python examples/motor_branch_circuit.py``);
:func:`motor_circuit` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    line_current_for_power,
    motor_branch_circuit_ampacity,
    motor_full_load_current,
)
from anvilate.units import Quantity

OUTPUT_POWER = Quantity.parse("15 kW")
LINE_VOLTAGE = Quantity.parse("400 V")
POWER_FACTOR = 0.85
EFFICIENCY = 0.90


def motor_circuit() -> dict[str, float]:
    """Return the naive current, the true full-load current, and the branch-circuit ampacity."""
    naive = line_current_for_power(
        real_power=OUTPUT_POWER, line_voltage=LINE_VOLTAGE, power_factor=POWER_FACTOR
    )
    flc = motor_full_load_current(
        output_power=OUTPUT_POWER,
        line_voltage=LINE_VOLTAGE,
        power_factor=POWER_FACTOR,
        efficiency=EFFICIENCY,
    )
    branch = motor_branch_circuit_ampacity(full_load_current=flc)
    return {
        "naive_a": naive.to("A").magnitude,
        "full_load_a": flc.to("A").magnitude,
        "branch_ampacity_a": branch.to("A").magnitude,
    }


def main() -> None:
    m = motor_circuit()
    print(f"naive (nameplate kW as draw)  : {m['naive_a']:.1f} A")
    print(f"motor full-load current       : {m['full_load_a']:.1f} A (input over efficiency)")
    print(f"branch-circuit ampacity (125%) : {m['branch_ampacity_a']:.1f} A (size conductor above)")
    print("  -> efficiency turns output into input; the NEC factor turns running current into wire")


if __name__ == "__main__":
    main()
