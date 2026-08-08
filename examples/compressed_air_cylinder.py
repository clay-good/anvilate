"""Worked example: the ideal gas law applied to a compressed-air cylinder.

The ideal gas law PV = nRT relates a gas's pressure, volume, amount, and temperature, and
rearranging it answers the everyday gas questions: what pressure a charge reaches, what volume it
fills when released, and how much gas a tank actually holds.

One mole of gas at 0 C (273.15 K) confined to 22.4 litres sits at about 101 kPa — one atmosphere,
the molar volume of any ideal gas at standard conditions. Released to 200 kPa at 300 K, 2 moles
occupy about 24.9 litres. And a 50 litre cylinder at 20 MPa and 15 C holds about 417 moles of gas —
roughly 12 kg of air. This example reports the pressure of the confined mole, the volume of the
released gas, and the moles in the cylinder.

Run it directly (``python examples/compressed_air_cylinder.py``);
:func:`cylinder_gas_state` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    ideal_gas_moles,
    ideal_gas_pressure,
    ideal_gas_volume,
)
from anvilate.units import Quantity


def cylinder_gas_state() -> dict[str, float]:
    """Return the confined pressure, the released volume, and the moles in the cylinder."""
    pressure = ideal_gas_pressure(
        amount=Quantity(magnitude=1.0, unit="mol"),
        volume=Quantity(magnitude=0.0224, unit="m**3"),
        temperature=Quantity(magnitude=273.15, unit="K"),
    )
    volume = ideal_gas_volume(
        amount=Quantity(magnitude=2.0, unit="mol"),
        pressure=Quantity(magnitude=200000.0, unit="Pa"),
        temperature=Quantity(magnitude=300.0, unit="K"),
    )
    moles = ideal_gas_moles(
        pressure=Quantity(magnitude=20e6, unit="Pa"),
        volume=Quantity(magnitude=0.05, unit="m**3"),
        temperature=Quantity(magnitude=288.15, unit="K"),
    )
    return {
        "confined_pressure_kpa": pressure.to("Pa").magnitude / 1000.0,
        "released_volume_l": volume.to("m**3").magnitude * 1000.0,
        "cylinder_moles": moles.to("mol").magnitude,
    }


def main() -> None:
    d = cylinder_gas_state()
    print(f"pressure of 1 mol in 22.4 L at 0 C: {d['confined_pressure_kpa']:.0f} kPa")
    print(f"volume of 2 mol at 200 kPa, 300 K: {d['released_volume_l']:.1f} L")
    print(f"moles in a 50 L cylinder at 20 MPa, 15 C: {d['cylinder_moles']:.0f} mol")


if __name__ == "__main__":
    main()
