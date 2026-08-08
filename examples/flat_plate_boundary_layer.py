"""Worked example: the laminar boundary layer on a flat plate.

Air flowing over a smooth flat plate builds a thin laminar boundary layer near the leading edge.
Blasius' solution fixes how thick that layer grows, how hard the flow scrapes the wall, and how much
friction drag the plate feels — all from the Reynolds number.

Air at 20 m/s (kinematic viscosity 1.5e-5 m^2/s) flows over a plate. At x = 0.1 m the local Reynolds
number is about 1.3e5 — comfortably laminar — so the boundary layer is only about 1.4 mm thick and
the local skin-friction coefficient is about 0.0018. Integrated over a 0.1 m plate, the average
drag coefficient of one face is about 0.0036, twice the trailing-edge skin friction. This example
reports the boundary-layer thickness, the local skin-friction coefficient, and the plate drag
coefficient.

Run it directly (``python examples/flat_plate_boundary_layer.py``);
:func:`plate_boundary_layer` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    laminar_boundary_layer_thickness,
    laminar_plate_drag_coefficient,
    laminar_skin_friction_coefficient,
)
from anvilate.units import Quantity

FREESTREAM_VELOCITY = Quantity(magnitude=20.0, unit="m/s")
DISTANCE = Quantity(magnitude=0.1, unit="m")
PLATE_LENGTH = Quantity(magnitude=0.1, unit="m")
KINEMATIC_VISCOSITY = Quantity(magnitude=1.5e-5, unit="m**2/s")  # air


def plate_boundary_layer() -> dict[str, float]:
    """Return the boundary-layer thickness, skin-friction coefficient, and drag coefficient."""
    delta = laminar_boundary_layer_thickness(
        freestream_velocity=FREESTREAM_VELOCITY,
        distance=DISTANCE,
        kinematic_viscosity=KINEMATIC_VISCOSITY,
    )
    cf = laminar_skin_friction_coefficient(
        freestream_velocity=FREESTREAM_VELOCITY,
        distance=DISTANCE,
        kinematic_viscosity=KINEMATIC_VISCOSITY,
    )
    cd = laminar_plate_drag_coefficient(
        freestream_velocity=FREESTREAM_VELOCITY,
        plate_length=PLATE_LENGTH,
        kinematic_viscosity=KINEMATIC_VISCOSITY,
    )
    return {
        "boundary_layer_thickness_mm": delta.to("m").magnitude * 1000.0,
        "skin_friction_coefficient": cf,
        "plate_drag_coefficient": cd,
    }


def main() -> None:
    d = plate_boundary_layer()
    print(f"boundary-layer thickness: {d['boundary_layer_thickness_mm']:.2f} mm")
    print(f"local skin-friction coefficient: {d['skin_friction_coefficient']:.4f}")
    print(f"plate drag coefficient: {d['plate_drag_coefficient']:.4f}")


if __name__ == "__main__":
    main()
