"""Worked example: the force, field, and potential around a point charge.

Coulomb's law and its field and potential describe everything a static charge does to its
surroundings: how hard it pushes another charge, how strong a field it sets up in empty space, and
what electric potential that field represents.

Two 1 microcoulomb charges a metre apart repel with about 9 mN — small, but far stronger than the
gravitational pull between the same objects. A single 1 microcoulomb charge sets up a field of about
900 kV/m at 10 cm away, and a potential of about 90 kV there. The field (force per charge) falls
off as the inverse square of distance while the potential (energy per unit charge) falls off only as
1/r. This example reports the Coulomb force, the field at 10 cm, and the potential at 10 cm.

Run it directly (``python examples/point_charge_field.py``);
:func:`point_charge_electrostatics` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    coulomb_force,
    electric_field_point_charge,
    electric_potential_point_charge,
)
from anvilate.units import Quantity

CHARGE = Quantity(magnitude=1e-6, unit="C")  # 1 microcoulomb
SEPARATION = Quantity(magnitude=1.0, unit="m")
DISTANCE = Quantity(magnitude=0.1, unit="m")  # 10 cm


def point_charge_electrostatics() -> dict[str, float]:
    """Return the Coulomb force, the field at 10 cm, and the potential at 10 cm."""
    force = coulomb_force(charge1=CHARGE, charge2=CHARGE, separation=SEPARATION)
    field = electric_field_point_charge(charge=CHARGE, distance=DISTANCE)
    potential = electric_potential_point_charge(charge=CHARGE, distance=DISTANCE)
    return {
        "coulomb_force_mn": force.to("N").magnitude * 1e3,
        "field_kv_m": field.to("V/m").magnitude / 1e3,
        "potential_kv": potential.to("V").magnitude / 1e3,
    }


def main() -> None:
    d = point_charge_electrostatics()
    print(f"Coulomb force (two 1 uC, 1 m): {d['coulomb_force_mn']:.2f} mN")
    print(f"field at 10 cm: {d['field_kv_m']:.0f} kV/m")
    print(f"potential at 10 cm: {d['potential_kv']:.0f} kV")


if __name__ == "__main__":
    main()
