"""Worked example: what a DC motor's two constants tell you at an operating point.

A permanent-magnet DC motor is almost fully described by two numbers — a back-EMF constant K_e and a
torque constant K_t, equal in SI — plus its armature resistance. This example takes a small motor
(K_e = K_t = 0.05, R_a = 1.5 Ω) running at 3000 rpm while drawing 2 A, and works out the three
quantities a drive designer needs: the back-EMF it generates, the torque it delivers, and the
terminal voltage the supply must hold.

At 3000 rpm the motor generates 15.7 V of back-EMF; adding the 3 V ohmic drop from 2 A through 1.5 Ω
means the driver must supply 18.7 V. The torque is set by current alone — 0.1 N·m — which is why the
same 2 A at stall (zero back-EMF) would need only 3 V but deliver the same torque, and why stall
current, if the supply held 18.7 V, would be a damaging 12.5 A.

Run it directly (``python examples/dc_motor_operating_point.py``);
:func:`operating_point` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    dc_motor_back_emf,
    dc_motor_terminal_voltage,
    dc_motor_torque,
)
from anvilate.units import Quantity

MOTOR_CONSTANT = Quantity.parse("0.05 V*s/rad")  # K_e = K_t in SI
ARMATURE_RESISTANCE = Quantity.parse("1.5 ohm")
SPEED = Quantity.parse("3000 rpm")
CURRENT = Quantity.parse("2 A")


def operating_point() -> dict[str, float]:
    """Return the back-EMF (V), torque (N·m), and required terminal voltage (V) at the point."""
    emf = dc_motor_back_emf(back_emf_constant=MOTOR_CONSTANT, angular_speed=SPEED)
    torque = dc_motor_torque(torque_constant=Quantity.parse("0.05 N*m/A"), armature_current=CURRENT)
    terminal = dc_motor_terminal_voltage(
        back_emf=emf, armature_current=CURRENT, armature_resistance=ARMATURE_RESISTANCE
    )
    return {
        "back_emf_v": emf.to("V").magnitude,
        "torque_nm": torque.to("N*m").magnitude,
        "terminal_voltage_v": terminal.to("V").magnitude,
    }


def main() -> None:
    p = operating_point()
    print("DC motor at 3000 rpm, 2 A (K_e = K_t = 0.05, R_a = 1.5 ohm):")
    print(f"  back-EMF          : {p['back_emf_v']:.2f} V")
    print(f"  torque            : {p['torque_nm']:.3f} N.m (set by current alone)")
    print(f"  terminal voltage  : {p['terminal_voltage_v']:.2f} V (back-EMF + I*R_a)")


if __name__ == "__main__":
    main()
