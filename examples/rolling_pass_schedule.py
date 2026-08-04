"""Worked example: why a rolling pass is limited by what the rolls can bite, not just the force.

Rolling a plate thinner seems like it should be limited only by how hard you can squeeze — how much
force the mill stand can take. But there is a quieter limit first: the rolls have to *grab* the
strip before they can reduce it, and friction can only drag so deep a bite before the strip skids
at the roll faces. That maximum draft, μ²·R, is set by the roll radius and the friction, and it caps
how much a single pass can remove regardless of how strong the mill is.

This example rolls a 200 mm wide steel strip on 500 mm diameter rolls (250 mm radius) with a die
friction of 0.3. The bite limit works out to a 22.5 mm maximum draft per pass — so a wanted 5 mm
reduction is comfortably feasible. Taking that 5 mm draft, the strip and rolls touch over a contact
length of about 35 mm, and at a 200 MPa average flow stress the rolls press on the strip with about
1,410 kN — roughly 145 tonnes, the force the stand and its bearings must carry. The example also
shows the other side of the bite limit: ask the same rolls for a greedy 30 mm reduction and it
exceeds the 22.5 mm they can grab, so the pass is infeasible on those rolls at that friction — you
would need bigger rolls, more friction, or to split it across passes. The point is that a pass
schedule is bounded from two directions at once: the mill's force capacity, and the humbler question
of whether the rolls can catch the strip at all.

Run it directly (``python examples/rolling_pass_schedule.py``);
:func:`rolling_pass` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import maximum_draft, rolling_contact_length, rolling_force
from anvilate.units import Quantity

ROLL_RADIUS = Quantity.parse("250 mm")  # 500 mm diameter rolls
FRICTION_COEFFICIENT = 0.3
STRIP_WIDTH = Quantity.parse("200 mm")
FLOW_STRESS = Quantity.parse("200 MPa")
WANTED_DRAFT = Quantity.parse("5 mm")
GREEDY_DRAFT = Quantity.parse("30 mm")


def rolling_pass() -> dict[str, float]:
    """Return the bite limit, the contact length and force of a pass, and a greedy-pass check."""
    max_draft = maximum_draft(roll_radius=ROLL_RADIUS, friction_coefficient=FRICTION_COEFFICIENT)
    contact = rolling_contact_length(roll_radius=ROLL_RADIUS, draft=WANTED_DRAFT)
    force = rolling_force(flow_stress=FLOW_STRESS, strip_width=STRIP_WIDTH, contact_length=contact)
    max_draft_mm = max_draft.to("mm").magnitude
    return {
        "max_draft_mm": max_draft_mm,
        "contact_length_mm": contact.to("mm").magnitude,
        "force_kn": force.to("kN").magnitude,
        "wanted_feasible": WANTED_DRAFT.to("mm").magnitude <= max_draft_mm,
        "greedy_feasible": GREEDY_DRAFT.to("mm").magnitude <= max_draft_mm,
    }


def main() -> None:
    p = rolling_pass()
    print(f"bite limit  : {p['max_draft_mm']:.1f} mm max draft (mu^2*R)")
    print(f"5 mm pass   : {'feasible' if p['wanted_feasible'] else 'infeasible'}")
    print(
        f"  contact {p['contact_length_mm']:.0f} mm, roll force {p['force_kn']:.0f} kN "
        f"(~{p['force_kn'] / 9.80665:.0f} tonnes)"
    )
    print(
        f"30 mm pass  : {'feasible' if p['greedy_feasible'] else 'infeasible'} "
        "-> exceeds the bite limit; split it or use bigger rolls"
    )


if __name__ == "__main__":
    main()
