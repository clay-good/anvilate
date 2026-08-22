"""QIF Results export: the scorecard as characteristics quality software can read.

Anvilate's scorecard is, structurally, what the metrology world already exchanges: a set
of characteristics, each with a requirement, an evaluated actual, and a status. That is
QIF (ISO 23952 / ANSI QIF 3.0), whose schemas are published free of charge. Writing the
evidence out as a QIF Results document makes Anvilate's verdicts consumable by CMM and
quality software without a licence fee and without a translator.

The mapping has three decisions in it, and each one is where the honesty lives:

**A check with a numeric requirement is a numeric characteristic.** A safety-factor check
becomes a ``UserDefinedUnitCharacteristic`` quartet whose nominal carries the required
minimum as ``MinValue`` with ``DefinedAsLimit`` true, because that is a limit and not a
deviation. A declared upper band is deliberately *not* written as a ``MaxValue`` — see
:func:`_numeric_requirement` — because in QIF a MaxValue is a conformance limit while
Anvilate's band is an over-engineering flag that never blocks. The measured value is the
computed safety factor, in the user-defined dimensionless unit declared once in
``FileUnits``.

**A check without one is an attribute characteristic, not an invented number.** A
deflection or serviceability check that carries only a verdict becomes a
``UserDefinedAttributeCharacteristic`` with ``PassValues``/``FailValues`` — QIF's own
attribute-gauge model. Nothing is fabricated to fill a numeric slot, which is what
inventing a nominal for a verdict-only check would amount to.

**Not-evaluated survives the crossing.** QIF has an enumeration for exactly this:
``NOT_ANALYZED``. A check that could not run is written as a characteristic that exists,
is named, cites its clause, and carries no value — never omitted, and never mapped to
``PASS``. The no-silent-green property is a property of the interchange file too, or it
was never a property at all: a reader that enumerates characteristics sees the gap.

``OVER_MARGIN`` has no QIF counterpart, because QIF has no notion of a check that passed
too well. It maps to ``PASS`` — it *is* a pass — with the over-margin finding stated in
the characteristic's ``Description`` so the signal crosses even though the enumeration
cannot carry it.

Traceability rides along: the spec digest and the bundle's roll-up go in the document
header, every citation the evidence collected becomes a ``Standard`` in
``StandardsDefinitions``, and every BOM component becomes a ``Software`` entry in
``SoftwareDefinitions`` — so the file says which Anvilate, against which databases,
screened which revision.

The document is deterministic: no timestamps, and the document UUID is derived from the
content rather than generated, so two identical bundles export byte-identical QIF. That
is the same property the attestation layer depends on, and a random ``QPId`` would have
destroyed it here.

Standard library only — QIF is XML, and ``xml.etree`` writes it. Validating an emitted
document against the published XSDs needs the schema package (a free download from
https://qifstandards.org/download/) and an XSD-capable parser; :func:`qif_schema_issues`
does the structural self-checks that do not need either, and the test suite's opt-in
schema test does the rest when a schema directory is pointed at it.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from decimal import Decimal
from hashlib import sha256
from math import isfinite
from xml.etree import ElementTree as ET

from ..attestation import EnvironmentBOM
from ..bundle import BundleSections
from ..evidence import SourceRecord
from ..scorecard import CheckStatus, ScorecardEntry

__all__ = [
    "QIF_NAMESPACE",
    "QIF_VERSION",
    "SAFETY_FACTOR_UNIT",
    "export_qif_results",
    "qif_schema_issues",
]

# The QIF 3.0 target namespace and the version stamp the root element must carry. Both
# are fixed by the schema package (ANSI QIF 3.0 / ISO 23952), not by us.
QIF_NAMESPACE = "http://qifstandards.org/xsd/qif3"
QIF_VERSION = "3.0.0"

# QIF types every numeric value against a named unit, and a safety factor is a ratio with
# no dimension — so it is declared once as a user-defined unit and every numeric
# characteristic references it by name. Declaring it beats borrowing a linear unit and
# hoping a reader ignores the dimension.
SAFETY_FACTOR_UNIT = "safetyFactor"

# The standards bodies QIF enumerates. A citation whose leading token is one of these is
# written as the enumerated organization; everything else (ASTM, AISC, AA, a handbook)
# goes through OtherStandardsOrganization, which is what the schema provides it for.
_QIF_ORGANIZATIONS = frozenset(
    {
        "AIAG",
        "ANSI",
        "ASAM",
        "ASME",
        "AWS",
        "BSI",
        "DIN",
        "DOD",
        "EASC",
        "GOST",
        "GOST_R",
        "IEC",
        "IEEE",
        "ISO",
        "JEITA",
        "JIS",
        "UL",
        "VDA",
        "W3C",
    }
)

# Anvilate's tri-state onto QIF's characteristic status enumeration. OVER_MARGIN is a
# pass in QIF's vocabulary because QIF has no "passed too well"; the finding itself is
# carried in the measurement's Description rather than dropped. NOT_EVALUATED lands on
# NOT_ANALYZED, which is QIF's own word for a characteristic nobody evaluated.
_CHARACTERISTIC_STATUS: dict[CheckStatus, str] = {
    CheckStatus.PASS: "PASS",
    CheckStatus.OVER_MARGIN: "PASS",
    CheckStatus.FAIL: "FAIL",
    CheckStatus.NOT_EVALUATED: "NOT_ANALYZED",
}

# The same roll-up onto the document-level InspectionStatus enumeration, which is a
# different (and differently spelled) list in the schema: it has NOT_CALCULATED where the
# characteristic list has NOT_ANALYZED. Mapping one from the other by string would have
# emitted an invalid document.
_INSPECTION_STATUS: dict[CheckStatus, str] = {
    CheckStatus.PASS: "PASS",
    CheckStatus.OVER_MARGIN: "PASS",
    CheckStatus.FAIL: "FAIL",
    CheckStatus.NOT_EVALUATED: "NOT_CALCULATED",
}

_PASS_VALUE = "pass"
_FAIL_VALUE = "fail"


def _decimal(value: float) -> str:
    """A float as an ``xs:decimal`` literal, at the value's own precision.

    ``xs:decimal`` admits neither exponent notation nor the non-finite specials, so the
    ordinary ``repr`` of a small or huge float ("1e-05", "inf") is not a legal value.
    Callers filter non-finite values out before they reach here; this fixes the notation.

    Fixed-point formatting at nine decimals looked like enough and was not. It rounded a
    failing safety factor of 1.9999999996 to "2.0" — exactly its own ``MinValue``, so a
    reader recomputing conformance from the limits called a FAIL conforming — and it wrote a
    positive requirement of 1e-12 as ``MinValue 0.0``, a limit every value on earth
    satisfies, which is the precise thing both ``_numeric_requirement`` and
    ``from_safety_factor`` refuse to let through the front door. ``Decimal`` over the
    float's own repr keeps every digit the float actually has, with no exponent.
    """
    if not isfinite(value):  # pragma: no cover - callers gate on _finite first
        raise ValueError(f"xs:decimal cannot represent {value!r}")
    return format(Decimal(repr(value)), "f")


def _finite(value: float | None) -> bool:
    """Whether a number is present and expressible as an ``xs:decimal``."""
    return value is not None and isfinite(value)


# The characters XML 1.0 does not admit at all, even escaped. A check name carrying one
# (from a pasted spreadsheet cell, say) produced a document no parser would open — and the
# self-check raised on it instead of reporting it, so the failure surfaced at the reader.
_ILLEGAL_XML = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _legal(text: str) -> str:
    """``text`` with characters XML cannot carry replaced, rather than emitted and lost."""
    return _ILLEGAL_XML.sub("\ufffd", text)


def _sub(parent: ET.Element, tag: str, text: str | None = None, **attrs: str) -> ET.Element:
    child = ET.SubElement(parent, tag, {k: _legal(v) for k, v in attrs.items()})
    if text is not None:
        child.text = _legal(text)
    return child


def _numeric_requirement(entry: ScorecardEntry) -> float | None:
    """The check's required minimum as a QIF limit, or ``None`` if it has no numeric one.

    A QIF numeric nominal needs a target and at least one limit. That needs a required
    minimum that is a real, positive number: an absent one (a verdict-only check), a
    non-finite one (the NaN cases the scorecard already reports as not-evaluated), or a
    non-positive one (which passes every check and which
    :meth:`ScorecardEntry.from_safety_factor` refuses at construction) cannot be written
    as a limit. Those checks cross as attribute characteristics instead, which is the
    honest shape: a verdict with no fabricated nominal under it.

    The declared **upper band is deliberately not exported as a QIF ``MaxValue``**. In QIF a
    MaxValue is a conformance limit and a value past it is nonconforming; in Anvilate the
    upper band is an over-engineering flag that never blocks anything. Writing one as the
    other produced a document whose own numbers said out-of-tolerance next to a status that
    said PASS, and a reader recomputing conformance from the limits would reject a part
    Anvilate's doctrine says is fine. The band travels in the characteristic's Description
    instead, where it cannot be mistaken for a tolerance.
    """
    required = entry.required_safety_factor
    if not _finite(required) or required <= 0:  # type: ignore[operator]
        return None
    return float(required)  # type: ignore[arg-type]


def _description(entry: ScorecardEntry, layer: str) -> str:
    """The characteristic's Description: which layer, the detail line, and the caveats.

    Anything the QIF enumerations cannot carry lands here rather than being lost — the
    over-margin finding, the repair hint on a failing check, and a fragility warning from
    an attached margin distribution.
    """
    parts = [f"{layer}: {entry.detail}"]
    if _finite(entry.upper_safety_factor):
        parts.append(
            f"target band {entry.required_safety_factor}-{entry.upper_safety_factor}: the "
            "upper bound is an over-engineering flag, not a conformance limit, so it is "
            "stated here rather than written as a QIF MaxValue"
        )
    if entry.status is CheckStatus.OVER_MARGIN:
        parts.append(
            "over-margin: this check passed above its declared target band; QIF has no "
            "status for an over-engineered pass, so it is reported here as PASS"
        )
    if entry.repair_hint is not None:
        parts.append(f"repair: {entry.repair_hint}")
    if entry.is_fragile():
        parts.append("fragile under the declared input scatter")
    return " | ".join(parts)


def _unique_names(names: Sequence[str]) -> list[str]:
    """The same names, made unique within the document, in order.

    A characteristic name is the key quality software joins on, and Anvilate's check names
    are not unique: `screen_structure` merges every member into one card, so two beams both
    contribute "B1 bending". The document itself stayed honest — distinct ids, distinct
    descriptions, one of them FAIL — but a reader keying by name saw one characteristic and
    kept whichever came last, which is how an overstressed member reads as passing.

    A repeat is suffixed with its occurrence number rather than dropped or merged, and an
    empty name gets a placeholder so the key exists at all. The original name stays in the
    Description either way.
    """
    taken: set[str] = set()
    out: list[str] = []
    for name in names:
        base = name.strip() or "unnamed check"
        # The candidate is checked against what has actually been emitted, not counted. A
        # card carrying "bending", "bending" and "bending #2" — which is what a re-import of
        # a previous Anvilate export looks like — made a counting version generate
        # "bending #2" twice, so the disambiguator produced the very collision it exists to
        # prevent, and one of the two was the FAIL. The suffix stacks when an input name
        # already looks like one ("bending #2 #2"); ugly, and unique, which is the property
        # that matters.
        candidate = base
        occurrence = 1
        while candidate in taken:
            occurrence += 1
            candidate = f"{base} #{occurrence}"
        taken.add(candidate)
        out.append(candidate)
    return out


class _Ids:
    """The document's QIF id counter. Ids are unique across the whole file."""

    def __init__(self) -> None:
        self._next = 0

    def take(self) -> str:
        self._next += 1
        return str(self._next)

    @property
    def maximum(self) -> int:
        return self._next


def _standard_element(parent: ET.Element, ids: _Ids, source: str, designator: str) -> str:
    """One citation as a QIF ``Standard``, returning its id."""
    identifier = ids.take()
    standard = _sub(parent, "Standard", id=identifier)
    organization = _sub(standard, "Organization")
    leading = source.split(" ", 1)[0].split("-", 1)[0].upper()
    if leading in _QIF_ORGANIZATIONS:
        _sub(organization, "StandardsOrganizationEnum", leading)
    else:
        _sub(organization, "OtherStandardsOrganization", source)
    _sub(standard, "Designator", designator)
    _sub(standard, "Title", source)
    return identifier


def _numeric_nominal(
    parent: ET.Element,
    ids: _Ids,
    *,
    definition_id: str,
    name: str,
    required: float,
) -> str:
    nominal_id = ids.take()
    nominal = _sub(parent, "UserDefinedUnitCharacteristicNominal", id=nominal_id)
    _sub(nominal, "CharacteristicDefinitionId", definition_id)
    _sub(nominal, "Name", name)
    # The target is the required minimum: the smallest factor the spec accepts is the
    # value the design is aimed at. Stating the upper band as the target instead would
    # report every compliant part as under-target.
    _sub(nominal, "TargetValue", _decimal(required), unitName=SAFETY_FACTOR_UNIT)
    # The schema's choice is MaxValue (optionally followed by MinValue) or MinValue alone.
    # This is always the second branch: the only real limit a screening check has is its
    # minimum, and see `_numeric_requirement` for why the target band is not written here.
    _sub(nominal, "MinValue", _decimal(required), unitName=SAFETY_FACTOR_UNIT)
    # These are limits on the value, not a ± band around the target.
    _sub(nominal, "DefinedAsLimit", "true")
    return nominal_id


def _attribute_nominal(parent: ET.Element, ids: _Ids, *, definition_id: str, name: str) -> str:
    nominal_id = ids.take()
    nominal = _sub(parent, "UserDefinedAttributeCharacteristicNominal", id=nominal_id)
    _sub(nominal, "CharacteristicDefinitionId", definition_id)
    _sub(nominal, "Name", name)
    passing = _sub(nominal, "PassValues", n="1")
    _sub(passing, "StringValue", _PASS_VALUE)
    failing = _sub(nominal, "FailValues", n="1")
    _sub(failing, "StringValue", _FAIL_VALUE)
    return nominal_id


def _characteristics(
    ids: _Ids,
    entries: Sequence[tuple[ScorecardEntry, str]],
    formal_standard_id: str,
) -> tuple[ET.Element, list[tuple[ScorecardEntry, str, str, bool]]]:
    """Build the Characteristics block.

    Returns the element and the per-entry records the measurement pass needs: the entry,
    its layer, its characteristic item id, and whether it was written as a numeric
    characteristic.
    """
    block = ET.Element("Characteristics")
    _sub(block, "FormalStandardId", formal_standard_id)
    definitions = _sub(block, "CharacteristicDefinitions", n=str(len(entries)))
    nominals = ET.Element("CharacteristicNominals", {"n": str(len(entries))})
    items = ET.Element("CharacteristicItems", {"n": str(len(entries))})
    records: list[tuple[ScorecardEntry, str, str, bool]] = []
    names = _unique_names([entry.name for entry, _layer in entries])

    for (entry, layer), name in zip(entries, names, strict=True):
        required = _numeric_requirement(entry)
        numeric = required is not None
        definition_id = ids.take()
        if numeric:
            definition = _sub(
                definitions, "UserDefinedUnitCharacteristicDefinition", id=definition_id
            )
            _sub(definition, "Description", _description(entry, layer))
            _sub(definition, "Name", name)
        else:
            definition = _sub(
                definitions, "UserDefinedAttributeCharacteristicDefinition", id=definition_id
            )
            _sub(definition, "Description", _description(entry, layer))
            _sub(definition, "Name", name)
            # WhatToMeasure follows the base type's elements in the schema sequence.
            _sub(definition, "WhatToMeasure", entry.reference or entry.name)

        if numeric:
            nominal_id = _numeric_nominal(
                nominals,
                ids,
                definition_id=definition_id,
                name=name,
                required=required,  # type: ignore[arg-type]
            )
            item_tag = "UserDefinedUnitCharacteristicItem"
        else:
            nominal_id = _attribute_nominal(nominals, ids, definition_id=definition_id, name=name)
            item_tag = "UserDefinedAttributeCharacteristicItem"

        item_id = ids.take()
        item = _sub(items, item_tag, id=item_id)
        if entry.reference:
            _sub(item, "Description", f"cites {entry.reference}")
        _sub(item, "Name", name)
        _sub(item, "CharacteristicNominalId", nominal_id)
        records.append((entry, layer, item_id, numeric))

    block.append(nominals)
    block.append(items)
    return block, records


def _measurements(
    ids: _Ids, records: Sequence[tuple[ScorecardEntry, str, str, bool]]
) -> ET.Element:
    """The measured characteristics: one actual per check, value only when there is one."""
    measured = ET.Element("MeasuredCharacteristics")
    block = _sub(measured, "CharacteristicMeasurements", n=str(len(records)))
    for entry, layer, item_id, numeric in records:
        tag = (
            "UserDefinedUnitCharacteristicMeasurement"
            if numeric
            else "UserDefinedAttributeCharacteristicMeasurement"
        )
        measurement = _sub(block, tag, id=ids.take())
        _sub(measurement, "Description", _description(entry, layer))
        status = _sub(measurement, "Status")
        _sub(status, "CharacteristicStatusEnum", _CHARACTERISTIC_STATUS[entry.status])
        _sub(measurement, "CharacteristicItemId", item_id)
        if numeric:
            # A not-evaluated check has no actual, and a non-finite one has no actual that
            # xs:decimal can express. Both leave Value out — the characteristic still
            # exists, still carries its status, and simply reports no number.
            if entry.evaluated and _finite(entry.safety_factor):
                _sub(
                    measurement,
                    "Value",
                    _decimal(float(entry.safety_factor)),  # type: ignore[arg-type]
                    unitName=SAFETY_FACTOR_UNIT,
                )
        elif entry.evaluated:
            _sub(measurement, "Value", _PASS_VALUE if entry.passed else _FAIL_VALUE)
    return measured


def _document_uuid(content: bytes) -> str:
    """A deterministic document UUID, derived from the content it identifies.

    QIF requires a UUID on every document. Generating a random one would make two exports of
    the same evidence differ byte for byte, destroying exactly the property the attestation
    layer spends its effort preserving — so this is a digest of the document itself, laid
    out in UUID form.

    It is a digest of the *whole serialized document* and not of a few identifying fields.
    Seeding it on the part name, the spec digest and the bundle's one-line summary looked
    equivalent and was not: two bundles differing in every safety factor, every citation and
    every BOM entry produced byte-different documents under one identifier — and the QPId is
    the key a QIF archive stores them under.

    The version nibble is 8 (RFC 9562's custom form) and not 5, because 5 would claim the
    value came from the SHA-1 namespace scheme and it did not. The variant bits are set so
    the value is a well-formed UUID rather than 32 hex characters wearing hyphens.
    """
    digest = bytearray(sha256(content).digest()[:16])
    digest[6] = (digest[6] & 0x0F) | 0x80  # version 8: custom, derived by this scheme
    digest[8] = (digest[8] & 0x3F) | 0x80  # RFC 9562 variant
    hexed = digest.hex()
    return f"{hexed[:8]}-{hexed[8:12]}-{hexed[12:16]}-{hexed[16:20]}-{hexed[20:]}"


# The placeholder the document carries while its own digest is being taken. It is a legal
# QPId so the intermediate serialization is a legal document, and it is replaced before the
# document is returned.
_QPID_PLACEHOLDER = "00000000-0000-8000-8000-000000000000"


def export_qif_results(
    sections: BundleSections,
    *,
    part_name: str,
    spec_digest: str,
    bom: EnvironmentBOM,
) -> str:
    """Export an evidence bundle's checks as a QIF Results document (ISO 23952).

    Every verdict in the bundle becomes a QIF characteristic: the analysis scorecard first,
    then the typed-callout scorecard when the bundle carries callouts, then the verification
    plan's items and the coverage it could not resolve — each tagged in its ``Description``
    with the layer it came from. Nothing is filtered: a check that could not run crosses as a
    ``NOT_ANALYZED`` characteristic with no value, so a reader enumerating the file sees the
    same gaps the scorecard reports.

    The layers that are *not* per-characteristic — the reviewer dossier, a design-space
    sweep — are disclosed in the header rather than invented as characteristics.

    ``spec_digest`` and ``bom`` are the traceability the requirement asks for: the digest
    identifies the spec revision screened, and every BOM component is written as a QIF
    ``Software`` entry, so the file records which toolchain and which versioned databases
    produced the verdicts. The bundle's citations become ``StandardsDefinitions``.

    Returns the document as XML text. It is deterministic — the same bundle exports the
    same bytes.
    """
    if not part_name.strip():
        raise ValueError("a QIF document needs the part it is about; part_name is empty")
    if not spec_digest.strip():
        raise ValueError(
            "a QIF export needs the digest of the spec revision it screened; without it "
            "the document says what passed but not what was checked"
        )

    layered: list[tuple[ScorecardEntry, str]] = [
        (entry, "analysis") for entry in sections.scorecard.entries
    ]
    callouts = sections.callout_card()
    if callouts is not None:
        layered.extend((entry, "callouts") for entry in callouts.entries)
    layered.extend((entry, "verification") for entry in _verification_entries(sections))

    ids = _Ids()
    root = ET.Element(
        "QIFDocument",
        {
            "xmlns": QIF_NAMESPACE,
            "versionQIF": QIF_VERSION,
            "idMax": "0",  # rewritten once every id has been handed out
        },
    )
    summary = sections.summary()
    qpid = _sub(root, "QPId", _QPID_PLACEHOLDER)

    header = _sub(root, "Header")
    application = _sub(header, "Application")
    _sub(application, "Name", bom.application.name)
    _sub(application, "Organization", "Anvilate")
    # The layers that are not per-characteristic are named here rather than left out. The
    # bundle's own summary — which states what it does and does not cover — is the one
    # sentence a reader has to be able to find, so it is not left to an f-string nobody
    # asserts on: `test_the_header_discloses_the_layers_that_are_not_characteristics` reads
    # it back.
    disclosed = [
        f"Analytical screening evidence for {part_name} (spec digest {spec_digest}).",
        summary,
    ]
    if sections.review is not None:
        disclosed.append(f"Reviewer dossier (not a characteristic): {sections.review.summary()}")
    if sections.exploration is not None:
        study = sections.exploration
        disclosed.append(
            "Design-space study (informational, not a characteristic): "
            f"{len(study.points)} candidates, {len(study.feasible)} feasible."
        )
    _sub(header, "Description", " ".join(disclosed))
    _sub(
        header,
        "Scope",
        "T1 analytical screening. These characteristics are screening results, not a "
        "certified analysis and not a physical inspection; a characteristic reported as "
        "NOT_ANALYZED was not evaluated and must not be read as conforming.",
    )

    # Standards: the formal standard the characteristics are evaluated against is QIF
    # itself when the bundle cites nothing else, then one entry per collected citation.
    standards = ET.Element("StandardsDefinitions")
    formal_standard_id = _standard_element(
        standards,
        ids,
        "ISO 23952 Quality Information Framework (QIF)",
        "ISO 23952",
    )
    for record in _citation_sources(sections.citations):
        _standard_element(standards, ids, record[1], record[0])
    standards.set("n", str(len(standards)))
    root.append(standards)

    software = ET.Element("SoftwareDefinitions")
    for component in (bom.application, *bom.components):
        entry = _sub(software, "Software", id=ids.take())
        _sub(entry, "VendorName", "Anvilate")
        _sub(entry, "ApplicationName", component.name)
        _sub(entry, "Version", component.version)
        _sub(entry, "Description", f"{component.kind.value} in the producing environment")
    software.set("n", str(len(software)))
    root.append(software)

    units = _sub(root, "FileUnits")
    _sub(units, "PrimaryUnits")
    user_units = _sub(units, "UserDefinedUnits", n="1")
    unit = _sub(user_units, "UserDefinedUnit")
    _sub(
        unit,
        "WhatIsMeasured",
        "safety factor — the dimensionless ratio of capacity to demand",
    )
    _sub(unit, "UnitName", SAFETY_FACTOR_UNIT)

    characteristics, records = _characteristics(ids, layered, formal_standard_id)
    root.append(characteristics)

    results = _sub(root, "Results")
    results_set = _sub(results, "MeasurementResultsSet", n="1")
    measurement_results = _sub(results_set, "MeasurementResults", id=ids.take())
    measurement_results.append(_measurements(ids, records))
    inspection_status = _sub(measurement_results, "InspectionStatus")
    _sub(inspection_status, "InspectionStatusEnum", _INSPECTION_STATUS[sections.status])

    root.set("idMax", str(ids.maximum))
    # The identifier is a digest of everything else in the document, so it is taken from the
    # serialization with the placeholder still in it and then substituted.
    qpid.text = _document_uuid(ET.tostring(root, encoding="utf-8"))
    return ET.tostring(root, encoding="unicode", xml_declaration=True) + "\n"


def _verification_entries(sections: BundleSections) -> list[ScorecardEntry]:
    """The verification plan's items as scorecard entries, for the crossing.

    A performed physical test is a verdict about the part, and it is characteristic-shaped:
    a name, an acceptance criterion, and a result. Leaving the plan out of the characteristic
    list produced the worst document this exporter can produce — a lifter whose proof test
    cracked it at 108% exported one PASS characteristic and a document-level FAIL, with the
    words "cracked" and "proof load" nowhere in the file. A reader recomputing the roll-up
    from the characteristics got PASS.

    Unresolved coverage crosses too, as a not-evaluated characteristic: a check that should
    have produced a test and did not is a gap, and a gap that is not in the file is a gap the
    file denies having.
    """
    plan = sections.verification
    if plan is None:
        return []
    # The plan's own roll-up, always. An empty plan produced no per-item entries at all, so
    # the bundle's status went NOT_EVALUATED while the characteristic list held nothing but
    # passes — a reader recomputing the roll-up from the characteristics got PASS, which is
    # the same denial of a gap the per-item crossing was added to fix.
    entries = [
        ScorecardEntry(
            name="verification plan",
            status=plan.status,
            detail=(
                f"{len(plan.verified)} of {len(plan.items)} planned tests performed, "
                f"{len(plan.analysis_only)} verified by analysis, "
                f"{len(plan.unresolved)} unresolved"
            ),
        )
    ]
    entries.extend(
        ScorecardEntry(
            name=item.name,
            status=item.status,
            detail=(
                f"{item.archetype.title} — acceptance: {item.acceptance}"
                + ("" if item.outcome is None else f"; recorded: {item.outcome.measured}")
            ),
            reference=item.archetype.citation,
        )
        for item in plan.items
    )
    entries.extend(
        ScorecardEntry(
            name=f"verification coverage: {check}",
            status=CheckStatus.NOT_EVALUATED,
            detail=f"no physical test could be planned — {reason}",
        )
        for check, reason in plan.unresolved
    )
    return entries


def _citation_sources(citations: Sequence[SourceRecord]) -> list[tuple[str, str]]:
    """Every distinct ``(designator, source)`` a bundle's citations carry, in order.

    One record can cite several standards, and two records routinely cite the same one —
    a materials handbook behind both the plate and the bolt. Duplicates are collapsed so
    the QIF standards list is a set of standards rather than a set of lookups.
    """
    seen: set[str] = set()
    out: list[tuple[str, str]] = []
    for record in citations:
        for source in record.sources:
            if source in seen:
                continue
            seen.add(source)
            out.append((record.name, source))
    return out


# What each internal reference is allowed to point at, by the local name of its target
# element. Checking only that a reference resolves to *some* id let a CharacteristicItemId
# point at a Software entry and pass clean, silently orphaning a verdict — the published
# schema catches that with a keyref, and a self-check that claims to check references has to
# check the same thing.
_REFERENCE_TARGETS: dict[str, str] = {
    "CharacteristicItemId": "CharacteristicItem",
    "CharacteristicNominalId": "CharacteristicNominal",
    "CharacteristicDefinitionId": "CharacteristicDefinition",
    "FormalStandardId": "Standard",
}


def qif_schema_issues(document: str) -> list[str]:
    """Structural problems in an emitted QIF document, as a list of complaints.

    The checks that do not need the schema package: the document parses at all, the root
    element and namespace, the ``idMax`` claim against the ids actually present, uniqueness
    of those ids, every ``n`` count against the children it counts, and every internal
    reference resolving to an id **of the right kind**. An empty list means the document is
    self-consistent — not that it is schema-valid, which requires the published XSDs and an
    XSD-capable parser.

    ``idMax`` is checked for equality rather than only for being large enough. The one-sided
    version passed a document claiming 999 ids while carrying 25, which is the same class of
    wrong as claiming too few and just as invisible to a reader.

    A document this cannot parse is reported as a complaint, not raised. A self-check that
    throws on the malformed input it exists to detect moves the failure to the reader.
    """
    issues: list[str] = []
    try:
        root = ET.fromstring(document)
    except ET.ParseError as exc:
        return [f"the document is not well-formed XML: {exc}"]
    if root.tag != f"{{{QIF_NAMESPACE}}}QIFDocument":
        issues.append(f"root element is {root.tag!r}, not a QIF document")
        return issues

    by_id: dict[str, str] = {}
    ids: list[str] = []
    for element in root.iter():
        identifier = element.get("id")
        if identifier is not None:
            ids.append(identifier)
            by_id.setdefault(identifier, _local(element.tag))
    if len(set(ids)) != len(ids):
        issues.append("the document reuses a QIF id; ids must be unique across the file")
    declared = int(root.get("idMax", "0"))
    numeric = [int(i) for i in ids if i.isdigit()]
    if numeric and max(numeric) != declared:
        issues.append(f"idMax is {declared} but the largest id in the document is {max(numeric)}")

    for element in root.iter():
        count = element.get("n")
        if count is None:
            continue
        if int(count) != len(element):
            issues.append(
                f"{_local(element.tag)} declares n={count} but carries {len(element)} children"
            )

    for element in root.iter():
        tag = _local(element.tag)
        # Only the declared references, not "every element whose name ends in Id". QIF has
        # plenty of the latter that are free text: `EmployeeId` and `EntityId` are
        # `xs:token`, and `EmployeeId` lives in a MeasurementResults traceability block —
        # inside the document class this module emits. Sweeping by suffix reported a
        # schema-valid document as broken, which is a self-check that cries wolf about the
        # thing it is supposed to certify. The cost is that a reference this exporter does
        # not write goes unchecked here; the XSD is what checks those.
        if tag not in _REFERENCE_TARGETS or not element.text:
            continue
        target = element.text.strip()
        if target not in by_id:
            issues.append(f"{tag} references id {target!r}, which is not in the document")
            continue
        expected = _REFERENCE_TARGETS[tag]
        if not by_id[target].endswith(expected):
            issues.append(
                f"{tag} references id {target!r}, which is a {by_id[target]} and not a {expected}"
            )
    return issues


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
