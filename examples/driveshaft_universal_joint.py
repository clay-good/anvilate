"""Worked example: the speed ripple of a driveshaft's universal joint.

A single Cardan universal joint lets a driveshaft turn a corner, but at a price: even with the input
spinning steadily, the output speeds up and slows down twice per revolution. The instantaneous speed
ratio, its peak value, and the peak-to-peak fluctuation tell you how rough that transmission is at a
given joint angle.

At a 20-degree shaft misalignment, the output speed swings from a peak of about 1.064 times the
input (when the driving fork lies in the plane of the shafts) down to about 0.940 a quarter-turn
later — a
peak-to-peak fluctuation of about 0.125, or 12.5% of the input speed. That ripple is why drivelines
pair two joints out of phase or use constant-velocity joints. This example reports the instantaneous
ratio at the peak, the maximum ratio, and the peak-to-peak speed fluctuation.

Run it directly (``python examples/driveshaft_universal_joint.py``);
:func:`joint_speed_ripple` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    universal_joint_max_speed_ratio,
    universal_joint_speed_fluctuation,
    universal_joint_speed_ratio,
)

SHAFT_ANGLE_DEG = 20.0


def joint_speed_ripple() -> dict[str, float]:
    """Return the peak instantaneous ratio, the maximum ratio, and the speed fluctuation."""
    ratio_at_peak = universal_joint_speed_ratio(shaft_angle=SHAFT_ANGLE_DEG, input_angle=0.0)
    max_ratio = universal_joint_max_speed_ratio(shaft_angle=SHAFT_ANGLE_DEG)
    fluctuation = universal_joint_speed_fluctuation(shaft_angle=SHAFT_ANGLE_DEG)
    return {
        "ratio_at_input_0deg": ratio_at_peak,
        "max_speed_ratio": max_ratio,
        "peak_to_peak_fluctuation": fluctuation,
    }


def main() -> None:
    d = joint_speed_ripple()
    print(f"speed ratio at input 0 deg: {d['ratio_at_input_0deg']:.4f}")
    print(f"maximum speed ratio: {d['max_speed_ratio']:.4f}")
    print(f"peak-to-peak fluctuation: {d['peak_to_peak_fluctuation']:.4f}")


if __name__ == "__main__":
    main()
