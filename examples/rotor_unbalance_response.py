"""Worked example: the running speed that turns a tiny unbalance into a big shake.

Every rotor has a little residual unbalance -- a gram of extra metal off-centre -- and
on its own it barely matters: spun slowly, this fan's unbalance would pull the shaft
off centre by only 0.02 mm, far inside the 0.10 mm vibration limit. What makes
unbalance dangerous is not its size but the speed you run it at relative to the
rotor's critical speed.

A forced mass-spring system amplifies a harmonic force by the dynamic magnification
factor 1/sqrt((1-r^2)^2 + (2*zeta*r)^2), where r is the running speed over the critical
speed. Well below the critical (r = 0.5) the factor is a mild 1.33 and the shake is
0.03 mm -- fine. Well above it (r = 2.0) the rotor cannot follow the force and the
factor drops to 0.33, quieter still. But run it just under the critical speed
(r = 0.95) and the lightly-damped factor spikes to 7.35: the same 0.02 mm unbalance
becomes a 0.15 mm vibration, half again over the limit. The unbalance did not change;
the speed put it on the resonance peak.

The lesson is that a rotor is sized against its unbalance *and* its critical speed
together: keep the running speed clear of the critical (below it, or accelerate
quickly through it to a super-critical speed), because near resonance even a trim
rotor shakes itself and its bearings apart. The unbalance, damping, and speeds are
declared inline.

Run it directly (``python examples/rotor_unbalance_response.py``);
:func:`screen_rotor_vibration` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import dynamic_magnification_factor
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

STATIC_UNBALANCE_DEFLECTION = Quantity.parse("0.02 mm")
DAMPING_RATIO = 0.05
VIBRATION_LIMIT = Quantity.parse("0.10 mm")
SPEED_RATIOS = {
    "well below critical (r = 0.5)": 0.5,
    "just under critical (r = 0.95)": 0.95,
    "super-critical (r = 2.0)": 2.0,
}


def screen_rotor_vibration() -> Scorecard:
    """Screen the amplified vibration amplitude against the limit at each running speed
    (safety factor = limit / amplitude)."""
    static = STATIC_UNBALANCE_DEFLECTION.to("mm").magnitude
    limit = VIBRATION_LIMIT.to("mm").magnitude
    entries = []
    for name, ratio in SPEED_RATIOS.items():
        magnification = dynamic_magnification_factor(
            frequency_ratio=ratio, damping_ratio=DAMPING_RATIO
        )
        amplitude = static * magnification
        entries.append(
            ScorecardEntry.from_safety_factor(name, computed=limit / amplitude, required=1.0)
        )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    static = STATIC_UNBALANCE_DEFLECTION.to("mm").magnitude
    for name, ratio in SPEED_RATIOS.items():
        magnification = dynamic_magnification_factor(
            frequency_ratio=ratio, damping_ratio=DAMPING_RATIO
        )
        print(
            f"{name}: magnification {magnification:.2f}, amplitude {static * magnification:.3f} mm"
        )
    print(screen_rotor_vibration())


if __name__ == "__main__":
    main()
