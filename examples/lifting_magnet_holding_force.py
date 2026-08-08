"""Worked example: how much a lifting electromagnet holds — field, pressure, then force.

An electromagnet grips steel through a short chain of physics: its coil sets up a magnetic field,
the field carries a pressure against any iron it touches, and that pressure over the pole face is
the holding force. Because the pressure — and so the force — grows with the square of the field, an
electromagnet is only as strong as the field it can drive across the contact, which is why a
clean, flat, thick plate holds far better than a thin or gappy one. Sizing a lifting magnet or a
magnetic clamp is walking that chain from coil to force.

This example energizes a solenoid coil at 1000 turns per metre and 2 A, which makes a modest 2.5 mT
field in air — but with an iron core and a closed magnetic circuit a real lifting magnet drives its
pole to about 1 tesla. At 1 T the Maxwell magnetic pressure is about 0.40 MPa, roughly 40 tonnes per
square metre of pole face. Over a 100 cm² (0.01 m²) pole in clean contact, that pressure becomes a
holding force of about 4.0 kN — enough to lift a ~400 kg plate. The example reports the bare-coil
field, the 1 T magnetic pressure, and the pole holding force, so the coil-to-clamp chain is clear.

Run it directly (``python examples/lifting_magnet_holding_force.py``);
:func:`lifting_magnet` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    electromagnet_holding_force,
    magnetic_pressure,
    solenoid_magnetic_field,
)
from anvilate.units import Quantity

TURNS_PER_LENGTH = Quantity.parse("1000 1/m")
COIL_CURRENT = Quantity.parse("2 A")
POLE_FLUX_DENSITY = Quantity.parse("1 T")  # iron-cored pole in a closed circuit
POLE_AREA = Quantity.parse("100 cm**2")


def lifting_magnet() -> dict[str, float]:
    """Return the bare-coil field, the 1 T magnetic pressure, and the pole holding force."""
    coil_field = solenoid_magnetic_field(turns_per_length=TURNS_PER_LENGTH, current=COIL_CURRENT)
    pressure = magnetic_pressure(magnetic_flux_density=POLE_FLUX_DENSITY)
    force = electromagnet_holding_force(
        magnetic_flux_density=POLE_FLUX_DENSITY, pole_area=POLE_AREA
    )
    return {
        "coil_field_mt": coil_field.to("mT").magnitude,
        "pole_pressure_mpa": pressure.to("MPa").magnitude,
        "holding_force_kn": force.to("kN").magnitude,
    }


def main() -> None:
    d = lifting_magnet()
    print(f"bare-coil field (1000 turns/m, 2 A): {d['coil_field_mt']:.1f} mT")
    print(f"magnetic pressure at 1 T pole: {d['pole_pressure_mpa']:.2f} MPa")
    print(
        f"holding force on a 100 cm^2 pole: {d['holding_force_kn']:.1f} kN "
        f"(~{d['holding_force_kn'] * 1000 / 9.80665:.0f} kg)"
    )


if __name__ == "__main__":
    main()
