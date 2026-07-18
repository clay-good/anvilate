"""Worked example: the stronger steel that was the more dangerous choice.

A highly stressed component runs at 400 MPa and is inspected in service by a
non-destructive method that can reliably find cracks down to 5 mm. Damage
tolerance asks a blunt question: is the crack that would cause fast fracture
bigger than the smallest crack inspection can catch? If not, a flaw can grow to
failure between inspections without ever being seen.

Two steels are on the table at the same 400 MPa. The high-strength steel has a
fracture toughness of 50 MPa*sqrt(m), which puts its critical crack length at
just 4.97 mm -- barely larger than the 5 mm inspection floor, and below the 2x
margin a safe interval needs (0.50). A crack could reach the critical size
between inspections undetected: the component fails without warning. The tougher
steel, at 100 MPa*sqrt(m), tolerates a 19.9 mm crack -- four times larger,
comfortably inspectable, a 1.99 margin.

Strength sizes a part against yield; toughness decides whether its cracks are
caught before they run. For a damage-tolerant design the material choice turns on
K_IC, not on strength alone -- and the stronger, more brittle steel is the more
dangerous one. The toughness values are material data, declared inline like any
allowable.

Run it directly (``python examples/fracture_toughness_screen.py``);
:func:`screen_fracture_toughness` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.analysis import critical_crack_length
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

OPERATING_STRESS = Quantity.parse("400 MPa")
DETECTABLE_CRACK = Quantity.parse("5 mm")
MARGIN = 2.0  # the critical crack must be at least this many times the detectable size

MATERIALS = {
    "high-strength steel (K_IC 50)": Quantity.parse("50 MPa*m**0.5"),
    "tough steel (K_IC 100)": Quantity.parse("100 MPa*m**0.5"),
}


def screen_fracture_toughness() -> Scorecard:
    """Screen each material: its critical crack length must exceed the detectable
    flaw size by the margin (safety factor = a_c / (detectable * margin))."""
    detectable = DETECTABLE_CRACK.to("mm").magnitude
    entries = []
    for name, toughness in MATERIALS.items():
        a_c = critical_crack_length(fracture_toughness=toughness, remote_stress=OPERATING_STRESS)
        entries.append(
            ScorecardEntry.from_safety_factor(
                name,
                computed=a_c.to("mm").magnitude / (detectable * MARGIN),
                required=1.0,
            )
        )
    return Scorecard(entries=tuple(entries))


def main() -> None:
    for name, toughness in MATERIALS.items():
        a_c = critical_crack_length(fracture_toughness=toughness, remote_stress=OPERATING_STRESS)
        print(f"{name}: critical crack {a_c.to('mm').magnitude:.2f} mm")
    print(screen_fracture_toughness())


if __name__ == "__main__":
    main()
