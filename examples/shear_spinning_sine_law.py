"""Worked example: why a steep spun cone must be made in stages — the sine law thins the wall.

Shear spinning forms a cone from a flat disc by rolling the metal down over a mandrel as it spins.
The outer diameter never changes; instead the wall thins, and by exactly how much is fixed by a
single elegant relation — the sine law, t_f = t₀·sin α, where α is the half-angle of the cone. A
gentle, near-flat cone barely thins the wall; a steep cone thins it hard. That makes the cone angle
and the wall thickness two views of the same thing, and it sets a limit: a cone steep enough to
demand more thinning than the metal can survive in one pass will tear, so steep cones are spun
in two or more stages with the reduction shared between them.

This example spins a 4 mm blank. At a 30° half-angle the sine law leaves a 2 mm wall — a 50%
reduction, aggressive but often within a single pass for a ductile alloy. Turn it around: to hit a
1.5 mm wall from the same 4 mm blank, the cone half-angle must be about 22°, a 62.5% reduction that
is likely too severe for one pass and would be split in two. The example reports the wall a 30° cone
gives, its reduction, and the steeper angle a 1.5 mm target demands, so the tie between cone angle,
wall thinning, and the need to stage a severe cut is explicit.

Run it directly (``python examples/shear_spinning_sine_law.py``);
:func:`spinning_case` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    shear_spinning_half_angle_for_thickness,
    shear_spinning_reduction,
    shear_spinning_wall_thickness,
)
from anvilate.units import Quantity

BLANK_THICKNESS = Quantity.parse("4 mm")
CONE_HALF_ANGLE = 30.0
TARGET_WALL = Quantity.parse("1.5 mm")


def spinning_case() -> dict[str, float]:
    """Return the wall a 30 deg cone gives, its reduction, and the angle a 1.5 mm wall needs."""
    wall = shear_spinning_wall_thickness(
        blank_thickness=BLANK_THICKNESS, half_cone_angle=CONE_HALF_ANGLE
    )
    reduction = shear_spinning_reduction(half_cone_angle=CONE_HALF_ANGLE)
    angle_for_target = shear_spinning_half_angle_for_thickness(
        blank_thickness=BLANK_THICKNESS, final_thickness=TARGET_WALL
    )
    reduction_for_target = shear_spinning_reduction(half_cone_angle=angle_for_target)
    return {
        "wall_at_30deg_mm": wall.to("mm").magnitude,
        "reduction_at_30deg": reduction,
        "angle_for_1p5mm_deg": angle_for_target,
        "reduction_for_1p5mm": reduction_for_target,
    }


def main() -> None:
    d = spinning_case()
    print(f"30 deg cone from a 4 mm blank -> {d['wall_at_30deg_mm']:.2f} mm wall")
    print(f"that is a {d['reduction_at_30deg']:.0%} reduction in one pass")
    print(
        f"a 1.5 mm wall needs a {d['angle_for_1p5mm_deg']:.0f} deg cone "
        f"({d['reduction_for_1p5mm']:.0%} reduction) -> likely spun in stages"
    )


if __name__ == "__main__":
    main()
