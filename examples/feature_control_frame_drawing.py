"""Worked example: one declaration, three consumers — text, QIF, and a drawing.

The same :class:`~anvilate.gdt.FeatureControlFrame` that ``render()`` writes as

    ⌖ | Ø0.2 mm Ⓜ | A | B Ⓜ | C

crosses into quality interchange as a QIF characteristic definition, and is drawn here as
the boxed, compartmented callout a drawing carries. Change one thing in the declaration —
add the Ø, promote RFS to Ⓜ, add a datum — and all three move together. A consumer that
quietly ignores a modifier is the failure this guards: on a drawing it is a callout looser
than the one declared, and in QIF it is one tighter.

**Every geometric symbol is drawn as geometry, not typeset as a character.** A ⌖ or an Ⓜ
written into a DXF as text renders correctly only where the viewer happens to have a font
carrying the glyph. Where it does not, the callout shows a tofu box or silently loses its
modifier, and the drawing then says something other than what the model declares. Lines
and arcs render the same everywhere, so only the digits of the tolerance and the datum
letters are left as text — and the permitted character set is closed, because the frame's
width allowance was checked for those characters and nothing else.

The proportions come from a published symbol chart (Genium *Drafting Manual* Section 6.1,
based on ASME Y14.5M-1994), which dimensions every symbol as a multiple of the character
height ``h``. Three would have been wrong from memory: symmetry is three lines of 2h, 1.2h
and 2h rather than an equals sign, the cylindricity tangents stand at 60°, and Ø's 1.5h is
the symbol's height rather than its slash's length.

Run it directly (``python examples/feature_control_frame_drawing.py``) to write
``position_callout.dxf`` and print the layout.
"""

from __future__ import annotations

from pathlib import Path

from anvilate.export.dxf import export_feature_control_frame_dxf
from anvilate.export.fcf import frame_drawing
from anvilate.export.qif import qif_characteristic_mapping
from anvilate.gdt import (
    Characteristic,
    DatumBoundary,
    DatumReference,
    FeatureControlFrame,
    FeatureType,
    FrameModifier,
    MaterialCondition,
)
from anvilate.units import Quantity

TEXT_HEIGHT = Quantity.parse("3.5 mm")  # ISO 3098's usual drawing character height


def hole_position_frame() -> FeatureControlFrame:
    """Position of a clearance hole, at MMC, to an ordered three-datum frame."""
    return FeatureControlFrame(
        characteristic=Characteristic.POSITION,
        tolerance=Quantity.parse("0.2 mm"),
        feature_type=FeatureType.FEATURE_OF_SIZE,
        material_condition=MaterialCondition.MMC,
        modifiers=(FrameModifier.DIAMETER,),
        datums=(
            DatumReference(letter="A"),
            DatumReference(letter="B", boundary=DatumBoundary.MMB, is_feature_of_size=True),
            DatumReference(letter="C"),
        ),
    )


def three_consumers(frame: FeatureControlFrame) -> tuple[str, str, tuple[float, ...]]:
    """The same declaration as text, as a QIF definition type, and as compartment edges."""
    mapping = qif_characteristic_mapping(frame)
    drawing = frame_drawing(frame, text_height=TEXT_HEIGHT)
    return frame.render(), mapping.definition_type, drawing.compartment_edges


def draw(dxf_path: str | Path) -> Path:
    """Write the callout to a DXF, on its own ``GDT`` annotation layer."""
    return export_feature_control_frame_dxf(
        frame=hole_position_frame(), path=dxf_path, text_height=TEXT_HEIGHT
    )


def main() -> None:
    frame = hole_position_frame()
    text, definition_type, edges = three_consumers(frame)
    drawing = frame_drawing(frame, text_height=TEXT_HEIGHT)

    print(f"text:    {text}")
    print(f"QIF:     {definition_type}, {drawing.labels[0].text} mm")
    print(f"drawing: {drawing.width:.2f} x {drawing.height:.2f} mm, {len(edges) - 1} compartments")
    for index, (left, right) in enumerate(zip(edges, edges[1:], strict=False)):
        print(f"           {index + 1}: {left:6.2f} .. {right:6.2f} mm")
    print(f"         {len(drawing.strokes)} strokes, {len(drawing.labels)} text runs")
    print("         (every symbol is geometry; only the value and datum letters are text)")

    # Drop the Ⓜ and watch all three move: the text loses its modifier, QIF drops from
    # MAXIMUM to REGARDLESS, and the drawn frame loses a glyph and narrows.
    # Rebuilt rather than model_copy'd: a copy skips the validators, and the legality
    # rules are the whole point of the model.
    rfs = FeatureControlFrame(**{**frame.model_dump(), "material_condition": MaterialCondition.RFS})
    rfs_text, _, rfs_edges = three_consumers(rfs)
    rfs_drawing = frame_drawing(rfs, text_height=TEXT_HEIGHT)
    print(f"\nsame frame at RFS: {rfs_text}")
    print(
        f"         QIF {qif_characteristic_mapping(rfs).material_modifier}, "
        f"drawing {rfs_drawing.width:.2f} mm wide "
        f"({drawing.width - rfs_drawing.width:.2f} mm narrower)"
    )

    path = draw("position_callout.dxf")
    print(f"\nwrote {path}")


if __name__ == "__main__":
    main()
