"""Tests for the standards-data provenance roll-up (evidence bundle slice)."""

from __future__ import annotations

import pytest

from anvilate.evidence import SourceRecord, collect_provenance
from anvilate.spec import (
    AcceptanceCriteria,
    DesignSpec,
    Manufacturing,
    ManufacturingProcess,
    MaterialRef,
    Provenanced,
    StandardComponentInterface,
    ToleranceDimension,
    ValidationTier,
)
from anvilate.standards import (
    UnknownMaterialError,
    default_components_db,
    default_materials_db,
)
from anvilate.tolerance import FitTolerance, SymmetricTolerance
from anvilate.units import Quantity, UnitSystem


def _spec(material: str = "AA-6061-T6", interfaces=None, dimensions=None) -> DesignSpec:
    return DesignSpec(
        name="probe",
        description="probe",
        units=Provenanced.stated(UnitSystem.SI),
        material=MaterialRef(ref=material),
        manufacturing=Manufacturing(process=ManufacturingProcess.CNC_MILLING),
        interfaces=interfaces if interfaces is not None else [],
        dimensions=dimensions if dimensions is not None else [],
        acceptance=AcceptanceCriteria(tiers=[ValidationTier.T0_GEOMETRY]),
    )


def test_collects_material_and_component_provenance() -> None:
    spec = _spec(interfaces=[StandardComponentInterface(ref="NEMA23", tag="bore")])
    records = collect_provenance(
        spec, materials=default_materials_db(), components=default_components_db()
    )

    assert [r.ref for r in records] == ["AA-6061-T6", "NEMA23"]
    assert [r.kind for r in records] == ["material", "component"]
    for record in records:
        assert isinstance(record, SourceRecord)
        assert record.sources  # at least one cited source
        # Sources are distinct and sorted.
        assert list(record.sources) == sorted(set(record.sources))


def test_material_only_spec_rolls_up_one_record() -> None:
    records = collect_provenance(
        _spec(), materials=default_materials_db(), components=default_components_db()
    )
    assert len(records) == 1
    assert records[0].kind == "material"


def test_iso286_fit_dimension_contributes_a_tolerance_source() -> None:
    # A fit dimension carries the ISO 286 citation; a user-declared ± band does
    # not, so only the fit shows up in the provenance trail.
    spec = _spec(
        dimensions=[
            ToleranceDimension(
                tag="pilot_bore",
                nominal=Quantity.parse("35 mm"),
                tolerance=FitTolerance(designation="H7"),
            ),
            ToleranceDimension(
                tag="slot_width",
                nominal=Quantity.parse("10 mm"),
                tolerance=SymmetricTolerance(plus_minus=Quantity.parse("0.05 mm")),
            ),
        ]
    )
    records = collect_provenance(
        spec, materials=default_materials_db(), components=default_components_db()
    )

    tolerance = [r for r in records if r.kind == "tolerance"]
    assert len(tolerance) == 1
    assert tolerance[0].ref == "pilot_bore"
    assert tolerance[0].name == "H7"
    assert tolerance[0].sources and all(tolerance[0].sources)


def test_unknown_material_ref_raises() -> None:
    with pytest.raises(UnknownMaterialError):
        collect_provenance(
            _spec(material="AA-9999-T0"),
            materials=default_materials_db(),
            components=default_components_db(),
        )
