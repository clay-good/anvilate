"""Worked example: sizing a lead shield for a Co-60 gamma source.

A gamma beam is cut down exponentially by shielding: each half-value layer of material halves what
gets through, so a shield is sized either by how much a given wall passes or by how thick a wall a
target reduction needs. This example does both for lead against Co-60's ~1.25 MeV gammas, where the
linear attenuation coefficient is about 0.0668 /mm.

That coefficient gives a half-value layer of about 10.4 mm — a centimetre of lead halves the beam.
A 50 mm lead wall (roughly five half-value layers) passes about 3.5% of the beam. If the goal is
a 1000-fold reduction (transmission 0.001, about ten half-value layers), the wall must be about
103 mm thick. These are narrow-beam figures that ignore scattered-photon build-up, so a real shield
carries some margin. The example reports the half-value layer, the transmission through 50 mm, and
the thickness needed for a 1000-fold cut.

Run it directly (``python examples/gamma_shield_thickness.py``);
:func:`size_lead_shield` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    half_value_layer,
    radiation_transmission_fraction,
    shield_thickness_for_transmission,
)
from anvilate.units import Quantity

LEAD_MU = Quantity(magnitude=0.0668, unit="1/mm")
WALL_THICKNESS = Quantity.parse("50 mm")
TARGET_TRANSMISSION = 0.001


def size_lead_shield() -> dict[str, float]:
    """Return the half-value layer, the 50 mm transmission, and the thickness for a 1000x cut."""
    hvl = half_value_layer(attenuation_coefficient=LEAD_MU)
    transmission = radiation_transmission_fraction(
        attenuation_coefficient=LEAD_MU, thickness=WALL_THICKNESS
    )
    thickness = shield_thickness_for_transmission(
        attenuation_coefficient=LEAD_MU, transmission_fraction=TARGET_TRANSMISSION
    )
    return {
        "half_value_layer_mm": hvl.to("mm").magnitude,
        "transmission_through_50mm": transmission,
        "thickness_for_1000x_mm": thickness.to("mm").magnitude,
    }


def main() -> None:
    d = size_lead_shield()
    print(f"half-value layer: {d['half_value_layer_mm']:.1f} mm")
    print(f"transmission through 50 mm: {d['transmission_through_50mm'] * 100:.1f}%")
    print(f"thickness for a 1000-fold cut: {d['thickness_for_1000x_mm']:.0f} mm")


if __name__ == "__main__":
    main()
