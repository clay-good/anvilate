"""Worked example: a piezoelectric force sensor — charge out, voltage generated, force read back.

A piezoelectric element turns force into charge with no power supply and no moving parts, which is
why it is the sensing element of load washers, impact sensors, and vibration energy harvesters. This
example runs the direct effect forward and back. Forward: how much charge a press produces (what a
charge amplifier or harvester collects), and what open-circuit voltage the same stress builds up.
Backward: the force a charge reading implies, which is how a piezo load washer is read out.

The element is a PZT-5H disc (d33 = 593 pC/N, g33 = 19.7 mV*m/N), 2 mm thick with a 1 cm^2 face. A
100 N press delivers about 59 nC of charge. Left open-circuit, the 1 MPa stress that 100 N makes
over the 1 cm^2 face builds about 39 V across the 2 mm gap — a large, easily measured signal from a
small push, and the reason unloaded piezo sensors need high-impedance front ends. Feeding the 59 nC
back through the inverse recovers the 100 N. The example reports the charge, the open-circuit
voltage, and the force recovered from the charge.

Run it directly (``python examples/piezo_force_sensor.py``);
:func:`force_sensor` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    piezoelectric_charge,
    piezoelectric_force_from_charge,
    piezoelectric_open_circuit_voltage,
)
from anvilate.units import Quantity

CHARGE_COEFFICIENT = Quantity(magnitude=593e-12, unit="C/N")
VOLTAGE_COEFFICIENT = Quantity(magnitude=19.7e-3, unit="V*m/N")
APPLIED_FORCE = Quantity.parse("100 N")
FACE_AREA = Quantity.parse("1 cm**2")
THICKNESS = Quantity.parse("2 mm")


def force_sensor() -> dict[str, float]:
    """Return the charge, the open-circuit voltage, and the force recovered from the charge."""
    charge = piezoelectric_charge(charge_coefficient=CHARGE_COEFFICIENT, force=APPLIED_FORCE)
    stress = Quantity(
        magnitude=APPLIED_FORCE.to("N").magnitude / FACE_AREA.to("m**2").magnitude, unit="Pa"
    )
    voltage = piezoelectric_open_circuit_voltage(
        voltage_coefficient=VOLTAGE_COEFFICIENT, stress=stress, thickness=THICKNESS
    )
    recovered_force = piezoelectric_force_from_charge(
        charge=charge, charge_coefficient=CHARGE_COEFFICIENT
    )
    return {
        "charge_nc": charge.to("nC").magnitude,
        "open_circuit_voltage_v": voltage.to("V").magnitude,
        "recovered_force_n": recovered_force.to("N").magnitude,
    }


def main() -> None:
    d = force_sensor()
    print(f"charge from a 100 N press: {d['charge_nc']:.1f} nC")
    print(f"open-circuit voltage: {d['open_circuit_voltage_v']:.1f} V")
    print(f"force recovered from the charge: {d['recovered_force_n']:.0f} N")


if __name__ == "__main__":
    main()
