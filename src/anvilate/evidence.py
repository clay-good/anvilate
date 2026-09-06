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

from pydantic import ConfigDict

from ._models import Named, Provenance, RevalidatedModel
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

__all__ = ["SourceRecord", "collect_provenance", "provenance_for"]


class SourceRecord(RevalidatedModel):
    """The provenance of one standards record a spec references.

    ``sources`` are the record's distinct citation sources, sorted — one entry
    per standard or dataset behind its dimensioned properties.
    """

    model_config = ConfigDict(frozen=True)

    ref: Provenance  # the referenced database ID or dimension tag, e.g. "AA-6061-T6"
    kind: Literal["material", "component", "tolerance"]
    name: Named  # the record's name, or a fit designation for a tolerance
    sources: tuple[str, ...]

    def __str__(self) -> str:
        """One line a reviewer reads, rather than pydantic's field dump.

        The exported bundle prints these, and until it did there was no surface that rendered
        a source record at all — so it printed
        ``ref='AA-6061-T6' kind='material' name='Aluminium 6061-T6' sources=(...)``. Every
        field is here, because a record is a provenance claim and a rendering that drops part
        of one is a provenance claim nobody made: `sources` says "none recorded" rather than
        collapsing to an empty pair of brackets, on the same rule the blocks around it follow.
        """
        listed = "; ".join(self.sources) or "none recorded"
        return f"{self.ref} ({self.kind}) {self.name} — {listed}"


# The governing standard for geometric tolerancing (feature control frames); a
# fixed reference, not a sourced dimension, so it is a constant rather than table
# data. ASME Y14.5 is the common alternative; ISO 1101 is Anvilate's baseline.
_GEOMETRIC_TOLERANCE_SOURCE = (
    "ISO 1101 — Geometrical product specifications (GPS) — Geometrical tolerancing"
)


def _distinct_sources(citations: dict[str, PropertyCitation]) -> tuple[str, ...]:
    """Each distinct source, with a strength's allowable basis stated alongside it.

    The basis was already in the provenance — as prose, inside a source string that said
    "specified minimum" or did not. Nothing could read it, so a reviewer comparing two
    records had to know which handbook table was a mean and which was a minimum. Now the
    roll-up says it: "ASM — AISI 4140 (typical)" against "ASTM A36 specified minimum
    (specification minimum)".
    """
    labelled = set()
    for cite in citations.values():
        if cite.basis is None:
            labelled.add(cite.source)
        else:
            labelled.add(f"{cite.source} ({cite.basis.value.replace('_', ' ')})")
    return tuple(sorted(labelled))


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


def provenance_for(spec: DesignSpec) -> tuple[SourceRecord, ...]:
    """The provenance trail for ``spec`` against the bundled databases, or ``()``.

    :func:`collect_provenance` takes its databases explicitly, which is right for a caller
    that has them and is why every one of its callers was a test: the two surfaces that
    build an evidence bundle — `anvilate export` and the `export_artifact` MCP tool — have a
    spec and nothing else, so neither called it and every bundle either shipped went out
    saying its sources were not recorded. One function both use, so the two cannot drift.

    **A reference that does not resolve returns no trail rather than raising.** Exporting is
    not the place that reports an unknown material: the scorecard in the same document
    already carries `material resolution` as a failing check naming the ref, and a bundle
    that refused to render because of it would withhold that finding from the reader who
    needs it. What must not happen is a *partial* trail presented as a whole one, which is
    why this is all-or-nothing rather than a per-record `try`.
    """
    from .standards import default_components_db, default_materials_db

    try:
        return tuple(
            collect_provenance(
                spec,
                materials=default_materials_db(),
                components=default_components_db(),
            )
        )
    except (KeyError, LookupError, ValueError):
        return ()
