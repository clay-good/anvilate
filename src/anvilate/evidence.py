"""Provenance roll-up for a spec's referenced standards data.

The evidence bundle an export ships must record where every number came from
(see openspec/specs/artifact-export/). This module builds the "material and
standards data provenance" slice of that bundle: given a :class:`DesignSpec` and
the databases its references resolve against, it walks the spec's material,
standard-component interfaces, the ISO 2768 general-tolerance class, the ISO 286
fit citations behind its toleranced dimensions, and ISO 1101 for any declared
geometric tolerances, collecting each referenced record's distinct citation
sources — the reproducibility trail an independent engineer follows.

The scorecard, FEA imagery, solver decks, and iteration history join the bundle
as those layers are built out.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from .spec import DesignSpec, StandardComponentInterface
from .standards import ComponentsDatabase, MaterialsDatabase, PropertyCitation
from .tolerance import general_tolerance_source, resolve_class

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


# The governing standard for geometric tolerancing (feature control frames); a
# fixed reference, not a sourced dimension, so it is a constant rather than table
# data. ASME Y14.5 is the common alternative; ISO 1101 is Anvilate's baseline.
_GEOMETRIC_TOLERANCE_SOURCE = (
    "ISO 1101 — Geometrical product specifications (GPS) — Geometrical tolerancing"
)


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
    standard-component interface, then the ISO 2768 general-tolerance class that
    governs every untoleranced dimension (always present — the default applies
    when the spec omits one), then one per toleranced dimension whose tolerance
    cites a standard (an ISO 286 fit designation carries its citation; a
    user-declared ± or limit band does not, so it is skipped), and finally ISO
    1101 once if the spec declares any geometric tolerances, all in declaration
    order. Imported interfaces reference another spec rather than a standards
    record, so they are skipped. Raises the database's unknown-reference error if
    a material or component ref does not resolve — run reference validation first
    to surface every such problem at once.
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
    # The ISO 2768 general class governs every untoleranced dimension — always,
    # via the default when the spec omits one — so it is always in the trail.
    general_class = resolve_class(spec.manufacturing.tolerance_class)
    records.append(
        SourceRecord(
            ref="general_tolerance",
            kind="tolerance",
            name=f"ISO 2768-{general_class.letter}",
            sources=(general_tolerance_source(),),
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
    # Any declared geometric tolerance (feature control frame) follows ISO 1101,
    # so cite it once when the spec declares any.
    if spec.geometric_tolerances:
        records.append(
            SourceRecord(
                ref="geometric_tolerances",
                kind="tolerance",
                name="ISO 1101 geometric tolerancing",
                sources=(_GEOMETRIC_TOLERANCE_SOURCE,),
            )
        )
    return records
