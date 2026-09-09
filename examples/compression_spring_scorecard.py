"""Worked example: one spring, one knob, two checks pulling opposite ways.

A long slender coil at a working force fails all three of its limits, and the two that name
the same parameter disagree about which way to move it: the solid-height clearance asks for
a longer spring (173.17 mm) and the lateral buckling asks for a shorter one. A caller who
acted on either alone would make the other worse. What this coil actually needs is a
different wire and fewer turns, and the card is what says so.

Run it directly (``python examples/compression_spring_scorecard.py``);
:func:`spring_limits` is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.packs.machinery import HelicalCompressionSpring, screen_compression_spring
from anvilate.units import Quantity


def _coil(**overrides: object) -> HelicalCompressionSpring:
    """A 1.6 mm music-wire coil, 40 turns on a 12 mm mean diameter, carrying 90 N."""
    fields: dict[str, object] = {
        "wire_diameter": Quantity.parse("1.6 mm"),
        "mean_coil_diameter": Quantity.parse("12 mm"),
        "active_coils": 38.0,
        "total_coils": 40.0,
        "free_length": Quantity.parse("150 mm"),
        "operating_force": Quantity.parse("90 N"),
        "shear_modulus": Quantity.parse("79.3 GPa"),
        "elastic_modulus": Quantity.parse("207 GPa"),
        "allowable_shear_stress": Quantity.parse("900 MPa"),
    }
    fields.update(overrides)
    return HelicalCompressionSpring(**fields)  # type: ignore[arg-type]


def spring_limits() -> dict[str, object]:
    """The three verdicts, and the parameter and direction each failing check names."""
    card = screen_compression_spring(_coil())
    return {
        "status": card.status.value,
        "factors": {e.name: round(e.safety_factor, 2) for e in card.entries},
        "levers": {
            e.name: (e.repair_hint.parameter, e.repair_hint.direction.value)
            for e in card.entries
            if e.repair_hint is not None
        },
        "clearance_length": next(
            e.repair_hint.corrective_value
            for e in card.entries
            if e.name == "solid-height clearance" and e.repair_hint is not None
        ),
    }


def main() -> None:
    limits = spring_limits()
    print(f"1.6 mm coil, 40 turns, 150 mm free: {str(limits['status']).upper()}")
    for name, factor in limits["factors"].items():  # type: ignore[union-attr]
        print(f"  {name:<24} n = {factor}")
    for name, (parameter, direction) in limits["levers"].items():  # type: ignore[union-attr]
        print(f"  {name:<24} {direction} {parameter}")
    print(f"  clearance wants a free length of {limits['clearance_length']:.2f} mm")
    print("  -> and buckling wants a shorter one; one knob, two directions")


if __name__ == "__main__":
    main()
