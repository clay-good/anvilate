"""Worked example: dragging a crate up a ramp against friction.

Dry friction sets how hard it is to move a load: the friction force it must overcome, the steepest
ramp it would rest on unaided, and the push needed to haul it up a real incline. All three follow
from the friction coefficient.

A crate weighing 1,000 N on a surface with a friction coefficient of 0.3 develops up to 300 N of
friction against a flat push. Left on a slope, it would just start to slide at an angle of repose of
about 16.7 degrees. To drag it up a 20-degree ramp — steeper than the repose angle, so it needs a
sustained push — takes about 624 N along the slope, gravity and friction adding together. This
example reports the flat-ground friction force, the angle of repose, and the ramp-haul force.

Run it directly (``python examples/crate_on_ramp.py``);
:func:`crate_friction` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    angle_of_repose,
    force_to_slide_up_incline,
    friction_force,
)
from anvilate.units import Quantity

WEIGHT = Quantity(magnitude=1000.0, unit="N")
FRICTION_COEFFICIENT = 0.3
RAMP_ANGLE_DEG = 20.0


def crate_friction() -> dict[str, float]:
    """Return the flat-ground friction force, the angle of repose, and the ramp-haul force."""
    friction = friction_force(normal_force=WEIGHT, friction_coefficient=FRICTION_COEFFICIENT)
    repose = angle_of_repose(friction_coefficient=FRICTION_COEFFICIENT)
    haul = force_to_slide_up_incline(
        weight=WEIGHT, incline_angle=RAMP_ANGLE_DEG, friction_coefficient=FRICTION_COEFFICIENT
    )
    return {
        "friction_force_n": friction.to("N").magnitude,
        "angle_of_repose_deg": repose.to("degree").magnitude,
        "ramp_haul_force_n": haul.to("N").magnitude,
    }


def main() -> None:
    d = crate_friction()
    print(f"flat-ground friction force: {d['friction_force_n']:.0f} N")
    print(f"angle of repose: {d['angle_of_repose_deg']:.1f} deg")
    print(f"force to haul up a 20-deg ramp: {d['ramp_haul_force_n']:.0f} N")


if __name__ == "__main__":
    main()
