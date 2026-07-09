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
from .standards import (
    BearingTable,
    ComponentsDatabase,
    MaterialsDatabase,
    PropertyCitation,
    default_bearing_table,
    default_cap_screw_table,
    default_dowel_pin_table,
    default_extrusion_table,
    default_hex_bolt_table,
    default_hex_nut_table,
    default_washer_table,
)
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


def _component_providers(components: ComponentsDatabase, bearings: BearingTable) -> list[tuple]:
    """The ordered set of component tables a ref is resolved against, each as a
    ``(has, get, describe)`` triple where ``describe(record) -> (ref_id, name)``.

    NEMA frames and bearings are the injected tables; the fastener and extrusion
    families use their bundled defaults (built once here, not per lookup). Every
    record type exposes ``citations()``, so the provenance walk is uniform.
    """
    dowels = default_dowel_pin_table()
    cap_screws = default_cap_screw_table()
    washers = default_washer_table()
    hex_nuts = default_hex_nut_table()
    hex_bolts = default_hex_bolt_table()
    extrusions = default_extrusion_table()
    return [
        (components.has_component, components.get, lambda c: (c.id, c.name)),
        (
            bearings.has_bearing,
            bearings.get,
            lambda b: (b.designation, f"ball bearing {b.designation}"),
        ),
        (dowels.has_pin, dowels.get, lambda d: (d.designation, f"dowel pin {d.designation}")),
        (
            cap_screws.has_screw,
            cap_screws.get,
            lambda s: (s.designation, f"cap screw {s.designation}"),
        ),
        (washers.has_washer, washers.get, lambda w: (w.designation, f"washer {w.designation}")),
        (hex_nuts.has_nut, hex_nuts.get, lambda n: (n.designation, f"hex nut {n.designation}")),
        (hex_bolts.has_bolt, hex_bolts.get, lambda b: (b.designation, f"hex bolt {b.designation}")),
        (extrusions.has_profile, extrusions.get, lambda p: (p.designation, p.name)),
    ]


def _component_source(
    ref: str, providers: list[tuple], components: ComponentsDatabase
) -> SourceRecord:
    """Resolve a standard-component ref to its provenance against the ordered
    component tables (NEMA frames, bearings, then the fastener and extrusion
    families). An unrecorded ref raises the components database's
    :class:`UnknownComponentError`."""
    for has, get, describe in providers:
        if has(ref):
            record = get(ref)
            ref_id, name = describe(record)
            return SourceRecord(
                ref=ref_id,
                kind="component",
                name=name,
                sources=_distinct_sources(record.citations()),
            )
    components.get(ref)  # no table matched → raise UnknownComponentError with near-misses
    raise AssertionError("unreachable")  # pragma: no cover


def collect_provenance(
    spec: DesignSpec,
    *,
    materials: MaterialsDatabase,
    components: ComponentsDatabase,
    bearings: BearingTable | None = None,
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
    to surface every such problem at once. A component interface may reference any
    bundled standard component (NEMA frame, ball bearing, dowel pin, cap screw,
    washer, hex nut, hex bolt, or T-slot extrusion); ``bearings`` defaults to the
    bundled table.
    """
    if bearings is None:
        bearings = default_bearing_table()
    providers = _component_providers(components, bearings)
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
            records.append(_component_source(interface.ref, providers, components))
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
