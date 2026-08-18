"""Worked example: five drawing callouts that do not parse, and one that does.

A feature control frame is a sentence with a grammar. Drawings carry it as symbols and
leave the checking to whoever reads it, which is why the same five errors keep reaching
the shop. Here the grammar lives in the constructor, so an illegal frame is not built.

The legal one, on a Ø8 H7 clearance hole:

    ⌖ | Ø0.2 mm Ⓜ | A | B Ⓜ | C

Position, a diametral zone of 0.2 at maximum material condition, located to an ordered
datum reference frame with a material boundary on B. Every part of that is checked: the
Ø needs a feature of size (a zone of an axis, and a surface has no axis), the Ⓜ needs one
too, B's Ⓜ needs B to be a feature of size, and three datums is the ceiling because three
is what constrains six degrees of freedom.

The five that are refused, each a real drawing error:

1. **Flatness to a datum.** Flatness is the surface against itself. A datum in the frame
   means the author meant parallelism, and the frame that says flatness will be inspected
   as flatness.
2. **Perpendicularity with no datum.** Perpendicular to *what*? An orientation control is
   a relationship and a relationship needs the other end.
3. **Ⓜ on a flatness callout.** A surface has no size, so it has no maximum material
   condition. The modifier does not tighten the control; it fails to parse.
4. **Symmetry on a 2018 drawing.** ASME Y14.5-2018 eliminated concentricity and symmetry
   — median-point controls that position or runout expresses better and almost nobody
   inspects correctly. On a 2009 drawing it is legal, and declaring the edition is the
   difference between a legacy callout and a mistake.
5. **Four datum references.** Three constrain six degrees of freedom; the fourth
   over-constrains and cannot be established.

Then the one number a GD&T callout owes the tolerance-stack layer: what a position
tolerance contributes to a 1D stack. A zone of total width t permits the axis anywhere
within ±t/2 of basic in any single direction, and for a diametral zone Ø t the extreme in
any one direction is likewise ±t/2. So Ø0.2 contributes ±0.1 mm, and at MMC with 0.1 mm of
bonus earned it contributes ±0.15 mm.

**That conversion is worst case and the docstring says so.** The true 2D distribution puts
most of the probability well inside the extreme, so feeding this half-band to an RSS or
Monte Carlo stack as a 1D uniform band overstates the spread — and gives a number that is
neither worst case nor statistical. Bonus tolerance is refused on an RFS frame outright:
it is not a conservative simplification, it is tolerance the drawing did not grant.

Run it directly (``python examples/feature_control_frame_legality.py``);
:func:`legal_frame` and :func:`illegal_frames` are exercised in the test suite.
"""

from __future__ import annotations

from anvilate.gdt import (
    Characteristic,
    DatumBoundary,
    DatumReference,
    FeatureControlFrame,
    FeatureType,
    FrameModifier,
    MaterialCondition,
    Y14Edition,
    position_stack_contribution,
)
from anvilate.units import Quantity


def legal_frame() -> FeatureControlFrame:
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


def illegal_frames() -> tuple[tuple[str, dict], ...]:
    """Five callouts that a drawing can carry and this model refuses to build."""
    surface = {"feature_type": FeatureType.SURFACE, "tolerance": Quantity.parse("0.05 mm")}
    return (
        (
            "flatness referencing a datum",
            {
                "characteristic": Characteristic.FLATNESS,
                "datums": (DatumReference(letter="A"),),
                **surface,
            },
        ),
        (
            "perpendicularity with no datum",
            {"characteristic": Characteristic.PERPENDICULARITY, **surface},
        ),
        (
            "Ⓜ on a surface callout",
            {
                "characteristic": Characteristic.FLATNESS,
                "material_condition": MaterialCondition.MMC,
                **surface,
            },
        ),
        (
            "symmetry on a 2018 drawing",
            {
                "characteristic": Characteristic.SYMMETRY,
                "feature_type": FeatureType.FEATURE_OF_SIZE,
                "tolerance": Quantity.parse("0.05 mm"),
                "datums": (DatumReference(letter="A"),),
            },
        ),
        (
            "four datum references",
            {
                "characteristic": Characteristic.POSITION,
                "feature_type": FeatureType.FEATURE_OF_SIZE,
                "tolerance": Quantity.parse("0.2 mm"),
                "datums": tuple(DatumReference(letter=x) for x in "ABCD"),
            },
        ),
    )


def legacy_symmetry() -> FeatureControlFrame:
    """The same symmetry callout, declared to the edition that still has it."""
    return FeatureControlFrame(
        characteristic=Characteristic.SYMMETRY,
        tolerance=Quantity.parse("0.05 mm"),
        feature_type=FeatureType.FEATURE_OF_SIZE,
        edition=Y14Edition.Y14_5_2009,
        datums=(DatumReference(letter="A"),),
    )


def main() -> None:
    frame = legal_frame()
    print(f"legal:   {frame.render()}")
    print(
        f"         class {frame.characteristic.characteristic_class.value}, "
        f"{len(frame.datums)} datums, diametral zone {frame.zone_is_diametral}"
    )

    print("\nrefused:")
    for label, kwargs in illegal_frames():
        try:
            FeatureControlFrame(**kwargs)
        except Exception as error:  # pydantic wraps the ValueError
            reason = str(error).split("\n")[1].strip().removeprefix("Value error, ")
            print(f"  {label}")
            print(f"    -> {reason[:96]}")

    legacy = legacy_symmetry()
    print(f"\nlegal on the earlier edition: {legacy.render()}   ({legacy.edition.value})")

    rfs = position_stack_contribution(frame)
    with_bonus = position_stack_contribution(frame, bonus=Quantity.parse("0.1 mm"))
    print(
        f"\n1D stack contribution of {frame.render()}:\n"
        f"  ±{rfs.magnitude:g} mm at MMC size, "
        f"±{with_bonus.magnitude:g} mm with 0.1 mm of bonus earned"
    )
    print("  (worst case, deliberately — an RSS stack fed this overstates the spread)")


if __name__ == "__main__":
    main()
