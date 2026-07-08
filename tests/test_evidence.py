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

    # Material, component, then the always-present ISO 2768 general class.
    assert [r.ref for r in records] == ["AA-6061-T6", "NEMA23", "general_tolerance"]
    assert [r.kind for r in records] == ["material", "component", "tolerance"]
    for record in records:
        assert isinstance(record, SourceRecord)
        assert record.sources  # at least one cited source
        # Sources are distinct and sorted.
        assert list(record.sources) == sorted(set(record.sources))


def test_material_only_spec_still_cites_the_general_class() -> None:
    # Even with no components or dimensions, the ISO 2768 default class governs
    # and appears in the trail — so the material and the general class both show.
    records = collect_provenance(
        _spec(), materials=default_materials_db(), components=default_components_db()
    )
    assert [r.kind for r in records] == ["material", "tolerance"]
    general = records[1]
    assert general.ref == "general_tolerance"
    assert general.name == "ISO 2768-m"  # medium is the ISO default
    assert general.sources and all(general.sources)


def test_declared_general_class_is_reflected() -> None:
    spec = _spec()
    spec = spec.model_copy(
        update={"manufacturing": spec.manufacturing.model_copy(update={"tolerance_class": "fine"})}
    )
    records = collect_provenance(
        spec, materials=default_materials_db(), components=default_components_db()
    )
    general = next(r for r in records if r.ref == "general_tolerance")
    assert general.name == "ISO 2768-f"


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

    # The general class plus exactly one per-dimension fit (the ± band is skipped).
    fits = [r for r in records if r.kind == "tolerance" and r.ref != "general_tolerance"]
    assert len(fits) == 1
    assert fits[0].ref == "pilot_bore"
    assert fits[0].name == "H7"
    assert fits[0].sources and all(fits[0].sources)


def test_unknown_material_ref_raises() -> None:
    with pytest.raises(UnknownMaterialError):
        collect_provenance(
            _spec(material="AA-9999-T0"),
            materials=default_materials_db(),
            components=default_components_db(),
        )
