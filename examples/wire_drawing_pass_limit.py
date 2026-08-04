"""Worked example: why wire is drawn through many dies, not one — the wire can only pull so hard.

Drawing reduces a wire by pulling it through a die, and that is its defining constraint: the force
comes from tension on the wire that just left the die, so the drawn wire itself has to carry the
whole draw stress. Ask a single die for too much reduction and the draw stress reaches the wire's
own strength — the wire necks and snaps at the die exit instead of drawing. That caps how much any
one pass can take, no matter how strong the bench pulling it.

This example draws a steel wire (400 MPa flow stress) through a die with a 6° semi-angle and a
friction coefficient of 0.05. The bite check first: the maximum area reduction the pass can take
before the wire breaks is about 49% — below the frictionless ideal of 63% (1 − 1/e), because
friction eats into the margin. A sensible working pass takes well under that, say a 20% reduction:
the draw
stress works out to about 132 MPa, comfortably a third of the wire's 400 MPa strength, and the draw
force on the reduced section is small. To take a wire from thick stock down to fine gauge — a
reduction of 90% or more overall — you cannot do it in one die; you string a dozen dies into a
drawing train, each taking a safe fraction, with the wire re-hardening between them. The example
computes the per-pass reduction limit and the draw stress of a working pass so the margin against
breakage is explicit — the number that decides how many dies the train needs.

Run it directly (``python examples/wire_drawing_pass_limit.py``);
:func:`drawing_limits` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import wire_drawing_force, wire_drawing_max_reduction, wire_drawing_stress
from anvilate.units import Quantity

FLOW_STRESS = Quantity.parse("400 MPa")
DIE_HALF_ANGLE = 6.0  # degrees
FRICTION_COEFFICIENT = 0.05
# A working pass: 20% area reduction (10 -> 8 mm^2).
INITIAL_AREA = Quantity.parse("10 mm**2")
FINAL_AREA = Quantity.parse("8 mm**2")


def drawing_limits() -> dict[str, float]:
    """Return the max reduction per pass and the draw stress/force of a 20% working pass."""
    max_reduction = wire_drawing_max_reduction(
        die_half_angle=DIE_HALF_ANGLE, friction_coefficient=FRICTION_COEFFICIENT
    )
    ideal_reduction = wire_drawing_max_reduction(
        die_half_angle=DIE_HALF_ANGLE, friction_coefficient=0.0
    )
    stress = wire_drawing_stress(
        flow_stress=FLOW_STRESS,
        initial_area=INITIAL_AREA,
        final_area=FINAL_AREA,
        die_half_angle=DIE_HALF_ANGLE,
        friction_coefficient=FRICTION_COEFFICIENT,
    )
    force = wire_drawing_force(drawing_stress=stress, final_area=FINAL_AREA)
    return {
        "max_reduction": max_reduction,
        "ideal_reduction": ideal_reduction,
        "pass_stress_mpa": stress.to("MPa").magnitude,
        "stress_ratio": stress.to("MPa").magnitude / FLOW_STRESS.to("MPa").magnitude,
        "pass_force_kn": force.to("kN").magnitude,
    }


def main() -> None:
    d = drawing_limits()
    print(
        f"max reduction/pass: {d['max_reduction']:.0%} "
        f"(frictionless ideal {d['ideal_reduction']:.0%} = 1 - 1/e)"
    )
    print(
        f"a 20% working pass: draw stress {d['pass_stress_mpa']:.0f} MPa "
        f"({d['stress_ratio']:.0%} of the 400 MPa wire strength), force {d['pass_force_kn']:.2f} kN"
    )
    print("  -> one die can't take a 90% reduction; string many dies into a drawing train")


if __name__ == "__main__":
    main()
