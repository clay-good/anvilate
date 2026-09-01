"""Worked example: one document, several members, one card.

A Design Spec says what kind of element the part is, and the screening pipeline
selects the discipline-pack screen from that. Until an assembly could be named,
that worked for one part at a time: a skid frame with two lifting padeyes had to
be screened as two separate documents, or as hand-built pack elements with the
document left behind.

``element_type: structure`` is the assembly. Its members are written with the
same ``element_type``/``element_params`` pair the top level uses, so a member is
the same declaration one level in, and each is dispatched to exactly the screen
it would have reached on its own.

The frame here carries two padeyes cut from the same A36 plate and lifted by the
same 60 kN sling leg. The front eye is the generous one — 120 mm wide and 20 mm
thick. The rear eye keeps the same 40 mm hole but was drawn 80 mm wide on a 10 mm
plate, and the two cuts do not reach the two ASME BTH-1 limit states the same
way. Net tension is taken across the width left beside the hole, so 80 mm at
20 mm thick becomes 40 mm at 10 mm: a quarter of the area, and the safety factor
falls from 6.67 to 1.67. Pin bearing is taken on the projected area of the hole,
which the width never enters, so halving the thickness halves it — 3.33 to 1.67.
Two different reductions landing on the same number, both under the 2.0 the
document itself demands, and the frame fails on both.

What the card shows that two separate runs would not is *which* member failed.
Every entry is prefixed with the member that produced it, so the two eyes'
identically named checks stay apart, and ``governing()`` names one of the rear
eye's — the frame is held back by the plate somebody thinned, not by the lift.

Run it directly (``python examples/skid_frame_document.py``);
:func:`screen_skid_frame` and :func:`screen_front_eye_only` are exercised in the
test suite.
"""

from __future__ import annotations

from anvilate.scorecard import Scorecard
from anvilate.screening import screen_spec
from anvilate.spec import (
    AcceptanceCriteria,
    Constraints,
    DesignSpec,
    Manufacturing,
    ManufacturingProcess,
    MaterialRef,
    Provenanced,
    ValidationTier,
)
from anvilate.units import Quantity, UnitSystem

REQUIRED_SF = 2.0


def _eye(name: str, *, width: str, thickness: str) -> dict:
    """One padeye, written the way a member of a structure is written."""
    return {
        "element_type": "lifting_lug",
        "element_params": {
            "name": name,
            "material": "ASTM-A36",
            "width": Quantity.parse(width),
            "hole_diameter": Quantity.parse("40 mm"),
            "thickness": Quantity.parse(thickness),
            "load": Quantity.parse("60 kN"),
        },
    }


def _document(element_type: str, element_params: dict) -> DesignSpec:
    return DesignSpec(
        name="skid frame",
        description="A lifting skid frame with a padeye at each end.",
        units=Provenanced.stated(UnitSystem.SI),
        material=MaterialRef(ref="ASTM-A36"),
        manufacturing=Manufacturing(process=ManufacturingProcess.SHEET_METAL),
        element_type=element_type,
        element_params=element_params,
        constraints=Constraints(min_safety_factor=Provenanced.stated(REQUIRED_SF)),
        acceptance=AcceptanceCriteria(tiers=[ValidationTier.T1_ANALYTICAL]),
    )


def skid_frame_spec() -> DesignSpec:
    """The document: a structure of two padeyes, front generous and rear thinned."""
    return _document(
        "structure",
        {
            "members": [
                _eye("front eye", width="120 mm", thickness="20 mm"),
                _eye("rear eye", width="80 mm", thickness="10 mm"),
            ]
        },
    )


def screen_skid_frame() -> Scorecard:
    """Both padeyes screened into one card, each entry naming its member."""
    return screen_spec(skid_frame_spec())


def screen_front_eye_only() -> Scorecard:
    """The same front eye declared on its own — the single-element path, unchanged."""
    front = _eye("front eye", width="120 mm", thickness="20 mm")
    return screen_spec(_document(front["element_type"], front["element_params"]))


def main() -> None:
    card = screen_skid_frame()
    print(f"skid frame: {card.status.value.upper()}")
    for entry in card.entries:
        print(f"  {entry.status.value:<14} {entry.name}")
        print(f"                 {entry.detail}")
    print(f"  governing:     {card.governing().name}")


if __name__ == "__main__":
    main()
