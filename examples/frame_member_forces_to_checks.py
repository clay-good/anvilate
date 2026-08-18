"""Worked example: someone else's frame analysis, Anvilate's cited checks.

A 6 m column from a portal frame, analysed in Pynite under LRFD 2 (1.2D + 1.6L), exported
at three stations. Anvilate did not compute these forces and does not pretend to — it
screens them, and the report says which tool produced them, at which version, under which
load case.

The whole example is about the door, not the check. Three things happen at it:

**The axis mapping is declared, never inferred.** The export calls major-axis bending M3
and minor-axis M2. Another tool calls them Mz and My, a third reverses them. Nothing in
the number says which, and screening a W-section's minor-axis moment as though it were
major overstates the flexural capacity by the ratio of the two section moduli — for this
section, **4.4×**. So the mapping is a typed declaration and an undeclared import is
refused.

**A component that is neither mapped nor ignored is an error.** The export carries P, M3,
M2, V2 and T. A mapping that names four of them and quietly drops the fifth produces a
check that never saw the torsion, and it comes back green. Here T is *ignored by name*,
with the reason recorded in the report — the model resists it through the slab diaphragm.
Dropping a component is an act, not an omission.

**The sign convention is declared too.** Most frame solvers report compression as
negative and Anvilate's beam-column screen takes it as positive, so
`axial_compression_positive` has no default. Import the −180 kN unflipped and the screen
reads a 180 kN *tension*, routes to AISC §H1.2 instead of §H1.1, and never checks the
column for buckling at all. It does not fail silently — it reports NOT_EVALUATED naming
the reason — but the point of the door is that the question gets asked before it arises.

**Each component governs at its own station.** The axial peak is at the base (−180 kN),
the major-axis moment at mid-height (148 kN·m), the shear at the base (95 kN). Collapsing
the member to a single station would screen all three at whichever one happened to win.
The bound demand carries a governing station per component.

Then the section: constants from `sectionproperties`, tagged with the tool, the version
and *how* — "warping analysis, 6-node triangles" is different provenance from "handbook
table". No shear form factor is supplied, and the library will report NOT_EVALUATED for a
transverse-shear screen rather than assume a rectangle's 1.5. An imported section is
exactly the case where guessing that would be wrong.

One guard is worth pointing at: if the imported minor-axis second moment exceeds the
major one, the axes are swapped and the import is refused. That is the single
transposition most likely to survive review, because both numbers look plausible.

Run it directly (``python examples/frame_member_forces_to_checks.py``); :func:`screen`
is exercised in the test suite.
"""

from __future__ import annotations

from anvilate.interop import (
    AxisMapping,
    ExternalSectionProperties,
    ForceComponent,
    ForceStation,
    MemberForceRecord,
    bind_demand,
    provenance_lines,
)
from anvilate.packs.structural import BeamColumnMember, screen_beam_column
from anvilate.scorecard import Scorecard
from anvilate.units import Quantity

MEMBER_LENGTH = Quantity.parse("6 m")
REQUIRED_SF = 1.0  # AISC interaction is unity at capacity; the factors are already in it

IGNORED = {"T": "torsion is resisted through the slab diaphragm, per the model notes"}


def imported_forces() -> MemberForceRecord:
    """The Pynite export: three stations, five components, one load case."""
    stations = tuple(
        ForceStation(
            position=Quantity(magnitude=position, unit="m"),
            components={
                "P": Quantity(magnitude=axial, unit="kN"),
                "M3": Quantity(magnitude=major, unit="kN*m"),
                "M2": Quantity(magnitude=4.0, unit="kN*m"),
                "V2": Quantity(magnitude=shear, unit="kN"),
                "T": Quantity(magnitude=1.2, unit="kN*m"),
            },
        )
        for position, axial, major, shear in (
            (0.0, -180.0, -120.0, 95.0),
            (3.0, -176.0, 148.0, 12.0),
            (6.0, -172.0, -96.0, -88.0),
        )
    )
    return MemberForceRecord(
        member="C-12 (portal column)",
        tool="Pynite",
        tool_version="1.1.0",
        load_case="LRFD 2: 1.2D + 1.6L",
        stations=stations,
    )


def mapping() -> AxisMapping:
    """M3 is major, M2 is minor, and T is dropped on purpose and by name."""
    return AxisMapping(
        labels={
            ForceComponent.AXIAL: "P",
            ForceComponent.MAJOR_BENDING: "M3",
            ForceComponent.MINOR_BENDING: "M2",
            ForceComponent.MAJOR_SHEAR: "V2",
        },
        # Pynite reports compression as negative; Anvilate's beam-column screen takes it
        # as positive. Declaring this is not paperwork: import the -180 kN unflipped and
        # the screen reads a 180 kN TENSION, routes to AISC §H1.2 instead of §H1.1, and
        # never checks the column for buckling at all.
        axial_compression_positive=False,
        ignored=tuple(IGNORED),
    )


def imported_section() -> ExternalSectionProperties:
    """Constants for a built-up section, meshed and integrated somewhere else."""
    return ExternalSectionProperties(
        name="BU-350x200 built-up I",
        source="sectionproperties",
        source_version="3.2.1",
        method="warping analysis, 6-node triangular mesh",
        area=Quantity.parse("9600 mm**2"),
        second_moment=Quantity.parse("2.05e8 mm**4"),
        extreme_fibre=Quantity.parse("175 mm"),
        second_moment_transverse=Quantity.parse("2.67e7 mm**4"),
        torsion_constant=Quantity.parse("5.9e5 mm**4"),
        # No shear form factor: the screen will say NOT_EVALUATED rather than assume one.
    )


def screen() -> tuple[Scorecard, tuple[str, ...]]:
    """Screen the imported demand on the imported section, with its provenance lines."""
    demand = bind_demand(imported_forces(), mapping())
    section = imported_section()
    member = BeamColumnMember(
        name=demand.member,
        section=section.cross_section(),
        length=MEMBER_LENGTH,
        axial_load=demand.components[ForceComponent.AXIAL],
        moment=demand.components[ForceComponent.MAJOR_BENDING],
        material="ASTM-A36",
    )
    card = screen_beam_column(member, required_safety_factor=REQUIRED_SF)
    return card, provenance_lines(demand=demand, section=section, ignored=IGNORED)


def major_over_minor_modulus() -> float:
    """How far a major/minor axis swap would overstate this section's flexural capacity."""
    section = imported_section()
    major = section.second_moment.to("mm**4").magnitude / 175.0
    minor = section.second_moment_transverse.to("mm**4").magnitude / 100.0
    return major / minor


def main() -> None:
    card, lines = screen()
    print(f"scorecard {card.status.value}")
    for entry in card.entries:
        factor = "  —  " if entry.safety_factor is None else f"{entry.safety_factor:.2f}"
        print(f"  {entry.name:<40} {entry.status.value:<14} SF {factor}")
    print("\nprovenance:")
    for line in lines:
        print(f"  {line}")
    print(
        f"\n  a major/minor axis swap on this section would overstate the flexural "
        f"capacity by {major_over_minor_modulus():.1f}x — which is why the mapping is "
        f"declared and not inferred"
    )


if __name__ == "__main__":
    main()
