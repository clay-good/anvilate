"""Worked example: a parallel-plate capacitor from geometry to field.

A parallel-plate capacitor is fixed by its geometry: the plate area, the gap, and the dielectric
between them set its capacitance, the voltage sets the charge it holds, and that voltage over the
gap sets the field the dielectric must withstand.

Two 0.01 m^2 plates (10 cm square) held 1 mm apart in air make a capacitance of about 88.5 pF.
Slipping in a dielectric of relative permittivity 4 quadruples it. Charged to 100 V, the air-gap
capacitor holds about 8.85 nC, and the field between the plates is 100 kV/m — well below air's
~3 MV/m breakdown, so it will not arc. This example reports the capacitance, the stored charge, and
the plate field.

Run it directly (``python examples/parallel_plate_capacitor.py``);
:func:`capacitor_state` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    capacitor_charge,
    parallel_plate_capacitance,
    parallel_plate_field,
)
from anvilate.units import Quantity

PLATE_AREA = Quantity(magnitude=0.01, unit="m**2")  # 10 cm square
SEPARATION = Quantity(magnitude=1e-3, unit="m")  # 1 mm
VOLTAGE = Quantity(magnitude=100.0, unit="V")


def capacitor_state() -> dict[str, float]:
    """Return the air-gap capacitance, the stored charge, and the plate field."""
    capacitance = parallel_plate_capacitance(
        plate_area=PLATE_AREA, separation=SEPARATION, relative_permittivity=1.0
    )
    charge = capacitor_charge(capacitance=capacitance, voltage=VOLTAGE)
    field = parallel_plate_field(voltage=VOLTAGE, separation=SEPARATION)
    return {
        "capacitance_pf": capacitance.to("F").magnitude * 1e12,
        "charge_nc": charge.to("C").magnitude * 1e9,
        "field_kv_m": field.to("V/m").magnitude / 1e3,
    }


def main() -> None:
    d = capacitor_state()
    print(f"capacitance: {d['capacitance_pf']:.1f} pF")
    print(f"stored charge at 100 V: {d['charge_nc']:.2f} nC")
    print(f"field between plates: {d['field_kv_m']:.0f} kV/m")


if __name__ == "__main__":
    main()
