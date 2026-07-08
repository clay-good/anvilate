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
    ValidationTier,
)
from anvilate.standards import (
    UnknownMaterialError,
    default_components_db,
    default_materials_db,
)
from anvilate.units import UnitSystem


def _spec(material: str = "AA-6061-T6", interfaces=None) -> DesignSpec:
    return DesignSpec(
        name="probe",
        description="probe",
        units=Provenanced.stated(UnitSystem.SI),
        material=MaterialRef(ref=material),
        manufacturing=Manufacturing(process=ManufacturingProcess.CNC_MILLING),
        interfaces=interfaces if interfaces is not None else [],
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


def test_unknown_material_ref_raises() -> None:
    with pytest.raises(UnknownMaterialError):
        collect_provenance(
            _spec(material="AA-9999-T0"),
            materials=default_materials_db(),
            components=default_components_db(),
        )
