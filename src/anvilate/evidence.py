"""Provenance roll-up for a spec's referenced standards data.

The evidence bundle an export ships must record where every number came from
(see openspec/specs/artifact-export/). This module builds the "material and
standards data provenance" slice of that bundle: given a :class:`DesignSpec` and
the databases its references resolve against, it walks the spec's material and
standard-component interfaces and collects each referenced record's distinct
citation sources — the reproducibility trail an independent engineer follows.

The scorecard, FEA imagery, solver decks, and iteration history join the bundle
as those layers are built out.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from .spec import DesignSpec, StandardComponentInterface
from .standards import ComponentsDatabase, MaterialsDatabase, PropertyCitation

__all__ = ["SourceRecord", "collect_provenance"]


class SourceRecord(BaseModel):
    """The provenance of one standards record a spec references.

    ``sources`` are the record's distinct citation sources, sorted — one entry
    per standard or dataset behind its dimensioned properties.
    """

    model_config = ConfigDict(frozen=True)

    ref: str  # the referenced database ID, e.g. "AA-6061-T6" or "NEMA23"
    kind: Literal["material", "component"]
    name: str
    sources: tuple[str, ...]


def _distinct_sources(citations: dict[str, PropertyCitation]) -> tuple[str, ...]:
    return tuple(sorted({cite.source for cite in citations.values()}))


def collect_provenance(
    spec: DesignSpec,
    *,
    materials: MaterialsDatabase,
    components: ComponentsDatabase,
) -> list[SourceRecord]:
    """Collect the provenance of the standards data ``spec`` references.

    Returns one :class:`SourceRecord` for the spec's material, then one for each
    standard-component interface, in declaration order. Imported interfaces
    reference another spec rather than a standards record, so they are skipped.
    Raises the database's unknown-reference error if a ref does not resolve — run
    reference validation first to surface every such problem at once.
    """
    material = materials.get(spec.material.ref)
    records = [
        SourceRecord(
            ref=material.id,
            kind="material",
            name=material.name,
            sources=_distinct_sources(material.citations()),
        )
    ]
    for interface in spec.interfaces:
        if isinstance(interface, StandardComponentInterface):
            component = components.get(interface.ref)
            records.append(
                SourceRecord(
                    ref=component.id,
                    kind="component",
                    name=component.name,
                    sources=_distinct_sources(component.citations()),
                )
            )
    return records
