"""Worked example: designing a biconvex lens from its glass and curvature.

A lens's focal length is set by its shape and its glass, not chosen directly. The lensmaker's
equation turns the surface curvatures and refractive index into a focal length, its reciprocal is
the power in diopters, and stacking a second lens combines their powers.

A symmetric biconvex lens of crown glass (index 1.5) with 0.1 m radii on both faces (front +0.1 m,
back -0.1 m) has a focal length of 0.1 m — a power of 10 diopters. Placing a second lens of 0.2 m
focal length in contact with it adds their powers, giving a combined focal length of about 0.067 m
(15 diopters). This example reports the lensmaker focal length, the lens power, and the combined
focal length of the pair.

Run it directly (``python examples/biconvex_lens_design.py``);
:func:`lens_design` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    combined_thin_lens_focal_length,
    lens_power,
    lensmaker_focal_length,
)
from anvilate.units import Quantity

REFRACTIVE_INDEX = 1.5  # crown glass
RADIUS_FRONT = Quantity(magnitude=0.1, unit="m")
RADIUS_BACK = Quantity(magnitude=-0.1, unit="m")
SECOND_LENS_FOCAL_LENGTH = Quantity(magnitude=0.2, unit="m")


def lens_design() -> dict[str, float]:
    """Return the lensmaker focal length, the lens power, and the combined focal length."""
    f = lensmaker_focal_length(
        refractive_index=REFRACTIVE_INDEX, radius1=RADIUS_FRONT, radius2=RADIUS_BACK
    )
    power = lens_power(focal_length=f)
    combined = combined_thin_lens_focal_length(
        focal_length1=f, focal_length2=SECOND_LENS_FOCAL_LENGTH
    )
    return {
        "focal_length_mm": f.to("m").magnitude * 1000.0,
        "power_diopters": power.to("1/m").magnitude,
        "combined_focal_length_mm": combined.to("m").magnitude * 1000.0,
    }


def main() -> None:
    d = lens_design()
    print(f"lensmaker focal length: {d['focal_length_mm']:.0f} mm")
    print(f"lens power: {d['power_diopters']:.0f} diopters")
    print(f"combined focal length with a 200 mm lens: {d['combined_focal_length_mm']:.1f} mm")


if __name__ == "__main__":
    main()
