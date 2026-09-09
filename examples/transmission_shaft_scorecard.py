"""Worked example: one shaft, three limits, three different diameters.

A transmission shaft is sized by static strength, by rotating-shaft fatigue, and by torsional
windup, and the three do not agree: strength and fatigue go as the cube of the diameter against
different allowables, and windup goes as the fourth power. This example screens a 40 mm shaft
that is comfortable on yielding (5.44) and on fatigue (3.59) and **fails** on windup (0.72), then
reads back what each failing check asks the diameter to become. A shaft sized on the static check
alone leaves here at 28.65 mm and twists five times its allowance.

Run it directly (``python examples/transmission_shaft_scorecard.py``);
:func:`shaft_limits` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.packs.machinery import TransmissionShaft, screen_shaft
from anvilate.units import Quantity


def _shaft(diameter: str) -> TransmissionShaft:
    """The same drive shaft at a chosen diameter: 250 N·m of bending, 400 N·m of torque."""
    return TransmissionShaft(
        diameter=Quantity.parse(diameter),
        bending_moment=Quantity.parse("250 N*m"),
        torque=Quantity.parse("400 N*m"),
        yield_strength=Quantity.parse("370 MPa"),
        length=Quantity.parse("600 mm"),
        shear_modulus=Quantity.parse("79.3 GPa"),
        allowable_twist=Quantity.parse("0.5 degree"),
        # The CORRECTED endurance limit: Marin factors and the keyway's fatigue stress
        # concentration are applied before the value arrives at the screen.
        endurance_limit=Quantity.parse("200 MPa"),
        ultimate_strength=Quantity.parse("690 MPa"),
    )


def shaft_limits() -> dict[str, object]:
    """The three safety factors at 40 mm, and the diameter each check asks for at 10 mm."""
    declared = screen_shaft(_shaft("40 mm"))
    # Undersized on purpose, so every check fails and every lever is on the card at once.
    undersized = screen_shaft(_shaft("10 mm"))
    return {
        "status": declared.status.value,
        "factors": {e.name: round(e.safety_factor, 2) for e in declared.entries},
        "wanted": {
            e.name: round(e.repair_hint.corrective_value, 2)
            for e in undersized.entries
            if e.repair_hint is not None
        },
    }


def main() -> None:
    limits = shaft_limits()
    print(f"40 mm shaft: {str(limits['status']).upper()}")
    for name, factor in limits["factors"].items():  # type: ignore[union-attr]
        print(f"  {name:<30} n = {factor}")
    print("each check, undersized, names the diameter that clears its own limit:")
    for name, diameter in limits["wanted"].items():  # type: ignore[union-attr]
        print(f"  {name:<30} d >= {diameter} mm")
    print("  -> the shaft is the largest of them, and it is not the strength one")


if __name__ == "__main__":
    main()
