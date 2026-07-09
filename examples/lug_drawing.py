"""Worked example: the full white-space vertical — check a lug, draw its DXF.

Declares a lifting lug, code-checks it with the structural pack (ASME BTH-1 net
tension and pin bearing), and exports its plan outline to a DXF a fabricator can
cut from. This is the project's competitive white space realized end to end: plain
inputs -> code-checked plate geometry -> DXF output, all deterministic and LLM-free.

Run it directly (``python examples/lug_drawing.py``) to write ``padeye.dxf`` and
print the scorecard; :func:`check_and_draw_lug` is also exercised in the test suite.
"""

from __future__ import annotations

from pathlib import Path

from anvilate.export.dxf import Hole, export_plate_dxf
from anvilate.packs.structural import LiftingLug, screen_lifting_lug
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

# The lug's plan geometry: an 80 mm-wide plate 120 mm tall with the 25 mm pin hole
# 90 mm up, centred.
WIDTH = Quantity.parse("80 mm")
HEIGHT = Quantity.parse("120 mm")
HOLE = Hole(x=Quantity.parse("40 mm"), y=Quantity.parse("90 mm"), diameter=Quantity.parse("25 mm"))


def check_and_draw_lug(dxf_path: str | Path) -> tuple[Scorecard, Path]:
    """Code-check the lug and export its outline; return the scorecard and DXF path."""
    lug = LiftingLug(
        name="padeye",
        width=WIDTH,
        hole_diameter=HOLE.diameter,
        thickness=Quantity.parse("16 mm"),
        load=Quantity.parse("50 kN"),
        material="ASTM-A36",
    )
    card = screen_lifting_lug(lug, required_safety_factor=1.5)
    path = export_plate_dxf(width=WIDTH, height=HEIGHT, holes=[HOLE], path=dxf_path)
    return card, path


def main() -> None:
    card, path = check_and_draw_lug("padeye.dxf")
    for entry in card.entries:
        print(entry)
    print(card)
    print(f"drawing written to {path}")


if __name__ == "__main__":
    main()
