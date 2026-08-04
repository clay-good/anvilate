"""Worked example: sizing a hydraulic drive from one number — the motor's displacement.

A positive-displacement hydraulic pump or motor is defined by its displacement D, the volume of oil
it sweeps per shaft revolution, and that one number ties the whole drive together. On the pump end,
displacement times speed sets the flow; on the motor end, displacement times pressure sets the
torque. Nothing else about the circuit changes those relations, which is what makes a hydraulic
drive so easy to size and so forgiving: the torque is there whenever the pressure is, at any speed.

This example takes a pump with a 50 cm³/rev displacement driven at 1500 rpm. Ideally it would
deliver 75 L/min, but a real gear pump leaks a little under load, so at 95% volumetric efficiency it
sends about 71 L/min into the circuit. That flow feeds a hydraulic motor of the same 50 cm³/rev
displacement, which sees a 200 bar pressure drop from the load. The motor's torque follows from the
displacement and the pressure alone: about 143 N·m after a 90% mechanical efficiency for friction —
and it holds that torque whether the shaft is barely creeping or spinning fast, because torque
tracks pressure, not speed. The motor's speed instead comes from the flow it is fed: the 71 L/min
drives it at about 1354 rpm, a little under the pump's 1500 because both machines leak. The example
computes the flow, the torque, and the motor speed so the drive can be checked end to end from that
single
displacement figure.

Run it directly (``python examples/hydraulic_motor_drive.py``);
:func:`size_hydraulic_drive` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    hydraulic_motor_speed,
    hydraulic_motor_torque,
    hydraulic_pump_flow_rate,
)
from anvilate.units import Quantity

DISPLACEMENT = Quantity(magnitude=50.0, unit="cm**3")  # 50 cc/rev, both pump and motor
PUMP_SPEED = Quantity(magnitude=1500.0, unit="rpm")
LOAD_PRESSURE_DROP = Quantity(magnitude=200.0, unit="bar")
VOLUMETRIC_EFFICIENCY = 0.95
MECHANICAL_EFFICIENCY = 0.90


def size_hydraulic_drive() -> dict[str, float]:
    """Return the pump flow, the motor torque, and the motor speed of the drive."""
    flow = hydraulic_pump_flow_rate(
        displacement=DISPLACEMENT,
        rotational_speed=PUMP_SPEED,
        volumetric_efficiency=VOLUMETRIC_EFFICIENCY,
    )
    torque = hydraulic_motor_torque(
        displacement=DISPLACEMENT,
        pressure_drop=LOAD_PRESSURE_DROP,
        mechanical_efficiency=MECHANICAL_EFFICIENCY,
    )
    speed = hydraulic_motor_speed(
        flow_rate=flow,
        displacement=DISPLACEMENT,
        volumetric_efficiency=VOLUMETRIC_EFFICIENCY,
    )
    return {
        "flow_lpm": flow.to("L/min").magnitude,
        "torque_nm": torque.to("N*m").magnitude,
        "motor_rpm": speed.to("rpm").magnitude,
    }


def main() -> None:
    d = size_hydraulic_drive()
    print(f"pump flow  : {d['flow_lpm']:.1f} L/min  (50 cc/rev at 1500 rpm, 95% volumetric)")
    print(f"motor torque: {d['torque_nm']:.0f} N*m  (200 bar across 50 cc/rev, 90% mechanical)")
    print(f"motor speed : {d['motor_rpm']:.0f} rpm  (set by the flow it is fed)")
    print("  -> one displacement figure sizes flow, torque, and speed end to end")


if __name__ == "__main__":
    main()
