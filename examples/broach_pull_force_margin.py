"""Worked example: why a broach cuts a little per tooth — the bar carries the force in tension.

Broaching finishes a keyway, spline, or slot in one stroke, each tooth of the long broach standing a
few hundredths of a millimetre proud of the last so the cut deepens as the bar passes through. Its
defining constraint is where the force goes: on a pull broach the entire cutting force is tension in
the bar, concentrated at the thinnest root between two gullets. Ask each tooth to bite too deep, or
let too many teeth cut at once, and the pull exceeds what that root can hold — the broach snaps, an
expensive tool destroyed mid-cut. That is why broaches are ground with modest rise per tooth and
generous roots: the design is governed by tension, not by the cut.

This example broaches a 12 mm wide slot through a 25 mm long workpiece with a broach of 8 mm tooth
pitch, 0.06 mm rise per tooth, cutting a steel of 2500 MPa specific cutting force. Three teeth are
in the cut at once, so the cutting force is about 5.4 kN. The broach's minimum root section is
120 mm² of HSS good for 300 MPa in tension, a pull capacity of 36 kN — a comfortable margin of
nearly 7. The example computes the force, the capacity, and their ratio so the margin against
snapping is explicit; it is what decides how aggressive a rise per tooth the broach may carry.

Run it directly (``python examples/broach_pull_force_margin.py``);
:func:`broach_margin` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import (
    broaching_cutting_force,
    broaching_pull_capacity,
    broaching_teeth_in_cut,
)
from anvilate.units import Quantity

WORKPIECE_LENGTH = Quantity.parse("25 mm")  # length of surface being broached
TOOTH_PITCH = Quantity.parse("8 mm")
RISE_PER_TOOTH = Quantity.parse("0.06 mm")
CUT_WIDTH = Quantity.parse("12 mm")
SPECIFIC_CUTTING_FORCE = Quantity.parse("2500 MPa")
# Pull broach minimum root section and its allowable tensile stress.
ROOT_AREA = Quantity.parse("120 mm**2")
ALLOWABLE_STRESS = Quantity.parse("300 MPa")


def broach_margin() -> dict[str, float]:
    """Return the teeth in cut, cutting force, pull capacity, and the margin against snapping."""
    teeth = broaching_teeth_in_cut(workpiece_length=WORKPIECE_LENGTH, tooth_pitch=TOOTH_PITCH)
    force = broaching_cutting_force(
        specific_cutting_force=SPECIFIC_CUTTING_FORCE,
        teeth_in_cut=teeth,
        cut_width=CUT_WIDTH,
        rise_per_tooth=RISE_PER_TOOTH,
    )
    capacity = broaching_pull_capacity(allowable_stress=ALLOWABLE_STRESS, root_area=ROOT_AREA)
    force_kn = force.to("kN").magnitude
    capacity_kn = capacity.to("kN").magnitude
    return {
        "teeth_in_cut": teeth,
        "cutting_force_kn": force_kn,
        "pull_capacity_kn": capacity_kn,
        "margin": capacity_kn / force_kn,
    }


def main() -> None:
    d = broach_margin()
    print(f"teeth in cut: {d['teeth_in_cut']}")
    print(
        f"cutting force {d['cutting_force_kn']:.1f} kN vs pull capacity "
        f"{d['pull_capacity_kn']:.0f} kN -> margin {d['margin']:.1f}x"
    )
    print("  -> modest rise per tooth keeps the tension well below what the root can hold")


if __name__ == "__main__":
    main()
