"""Provenance roll-up for a spec's referenced standards data.

The evidence bundle an export ships must record where every number came from
(see openspec/specs/artifact-export/). This module builds the "material and
standards data provenance" slice of that bundle: given a :class:`DesignSpec` and
the databases its references resolve against, it walks the spec's material,
standard-component interfaces, and the ISO 286 fit citations behind its
toleranced dimensions, collecting each referenced record's distinct citation
sources — the reproducibility trail an independent engineer follows.

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

    ref: str  # the referenced database ID or dimension tag, e.g. "AA-6061-T6"
    kind: Literal["material", "component", "tolerance"]
    name: str  # the record's name, or a fit designation for a tolerance
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

    Returns one :class:`SourceRecord` for the spec's material, then one per
    standard-component interface, then one per toleranced dimension whose
    tolerance cites a standard (an ISO 286 fit designation carries its citation;
    a user-declared ± or limit band does not, so it is skipped), all in
    declaration order. Imported interfaces reference another spec rather than a
    standards record, so they are skipped. Raises the database's
    unknown-reference error if a material or component ref does not resolve — run
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
    for dimension in spec.dimensions:
        resolved = dimension.resolve()
        if resolved.source is not None:
            records.append(
                SourceRecord(
                    ref=dimension.tag,
                    kind="tolerance",
                    name=resolved.label,
                    sources=(resolved.source,),
                )
            )
    return records
