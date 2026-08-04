"""Worked example: sizing a vertical ball-screw axis — the drive motor and the holding brake.

A ball screw lifts a load efficiently, but that same efficiency means it will not hold the load on
its own — cut the power and the weight spins the screw back down. This example sizes a vertical axis
that raises a 4 kN load on a 10 mm-lead ball screw at 90% forward efficiency. It first finds the
drive torque the motor needs to push the load up, then the back-driving torque the suspended load
applies through the screw when the drive is unpowered, which a holding brake (or the motor's detent)
resist to keep the axis from creeping down. The drive torque is the motor-sizing number; the
back-drive torque is the brake-sizing number, and on a vertical ball-screw axis you need both — the
lesson an acme-screw designer, whose self-locking screw needs no brake, sometimes forgets.

Run it directly (``python examples/vertical_ball_screw_axis.py``);
:func:`axis_torques` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import ball_screw_back_drive_torque, ball_screw_drive_torque
from anvilate.units import Quantity

AXIAL_LOAD = Quantity.parse("4000 N")
LEAD = Quantity.parse("10 mm")
FORWARD_EFFICIENCY = 0.90
BACK_DRIVE_EFFICIENCY = 0.80


def axis_torques() -> dict[str, float]:
    """Return the drive torque and the back-driving torque (N·m) for the vertical axis."""
    drive = ball_screw_drive_torque(axial_load=AXIAL_LOAD, lead=LEAD, efficiency=FORWARD_EFFICIENCY)
    back = ball_screw_back_drive_torque(
        axial_load=AXIAL_LOAD, lead=LEAD, back_drive_efficiency=BACK_DRIVE_EFFICIENCY
    )
    return {
        "drive_torque_nm": drive.to("N*m").magnitude,
        "back_drive_torque_nm": back.to("N*m").magnitude,
    }


def main() -> None:
    t = axis_torques()
    print(f"drive torque (motor sizing)       : {t['drive_torque_nm']:.2f} N·m")
    print(f"back-driving torque (brake sizing): {t['back_drive_torque_nm']:.2f} N·m")
    print("  -> the ball screw is not self-locking; the suspended load needs a holding brake")


if __name__ == "__main__":
    main()
