"""Worked example: the evidence trail behind a spec's standards data.

Anvilate's promise is geometry an engineer can trust *with the evidence attached*.
This example builds a small Design Spec for a motor-mount bracket — an aluminum
part that seats a NEMA 23 stepper and a 6204 ball bearing, carries an ISO 286 H7
pilot bore, and calls out a flat mounting face — and rolls up every standards
record it leans on into an auditable provenance bundle.

:func:`collect_provenance` walks the spec and returns one record per source: the
material, each standard component, the ISO 2768 general-tolerance class that
always applies, the ISO 286 fit on the toleranced bore, and ISO 1101 for the
geometric call-out — each naming the standard or dataset behind it. Nothing is
asserted without a citation; this is what a design review reads.

Run it directly (``python examples/evidence_bundle.py``); :func:`build_evidence`
is also exercised in the test suite.
"""

from __future__ import annotations

from anvilate.evidence import SourceRecord
from anvilate.evidence import collect_provenance as _collect
from anvilate.spec import (
    AcceptanceCriteria,
    DesignSpec,
    GeometricCharacteristic,
    GeometricTolerance,
    Manufacturing,
    ManufacturingProcess,
    MaterialRef,
    Provenanced,
    StandardComponentInterface,
    ToleranceDimension,
    ValidationTier,
)
from anvilate.standards import default_components_db, default_materials_db
from anvilate.tolerance import FitTolerance
from anvilate.units import Quantity, UnitSystem


def _spec() -> DesignSpec:
    return DesignSpec(
        name="motor_mount_bracket",
        description="Aluminum bracket seating a NEMA 23 stepper and a 6204 bearing.",
        units=Provenanced.stated(UnitSystem.SI),
        material=MaterialRef(ref="AA-6061-T6"),
        manufacturing=Manufacturing(process=ManufacturingProcess.CNC_MILLING),
        interfaces=[
            StandardComponentInterface(ref="NEMA23", tag="motor_face"),
            StandardComponentInterface(ref="6204", tag="output_bearing"),
        ],
        dimensions=[
            ToleranceDimension(
                tag="pilot_bore",
                nominal=Quantity.parse("35 mm"),
                tolerance=FitTolerance(designation="H7"),
            ),
        ],
        geometric_tolerances=[
            GeometricTolerance(
                characteristic=GeometricCharacteristic.FLATNESS,
                tolerance=Quantity.parse("0.05 mm"),
                feature="motor_face",
            ),
        ],
        acceptance=AcceptanceCriteria(tiers=[ValidationTier.T0_GEOMETRY]),
    )


def build_evidence() -> list[SourceRecord]:
    """Roll the spec's referenced standards data up into a provenance bundle."""
    return _collect(_spec(), materials=default_materials_db(), components=default_components_db())


def main() -> None:
    for record in build_evidence():
        sources = "; ".join(record.sources)
        print(f"[{record.kind}] {record.ref} ({record.name}) <- {sources}")


if __name__ == "__main__":
    main()
