"""QIF Results export: the scorecard as characteristics quality software can read.

Anvilate's scorecard is, structurally, what the metrology world already exchanges: a set
of characteristics, each with a requirement, an evaluated actual, and a status. That is
QIF (ISO 23952 / ANSI QIF 3.0), whose schemas are published free of charge. Writing the
evidence out as a QIF Results document makes Anvilate's verdicts consumable by CMM and
quality software without a licence fee and without a translator.

The mapping has three decisions in it, and each one is where the honesty lives:

**A check with a numeric requirement is a numeric characteristic.** A safety-factor check
becomes a ``UserDefinedUnitCharacteristic`` whose nominal carries the required minimum as
``MinValue`` and — when the spec declared a target band — the upper bound as ``MaxValue``,
with ``DefinedAsLimit`` true because those are limits, not deviations. The measured value
is the computed safety factor, in the user-defined dimensionless unit declared once in
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

from collections.abc import Sequence
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
    """A float as an ``xs:decimal`` literal.

    ``xs:decimal`` admits neither exponent notation nor the non-finite specials, so the
    ordinary ``repr`` of a small or huge float ("1e-05", "inf") is not a legal value.
    Callers filter non-finite values out before they reach here; this fixes the notation.
    """
    if not isfinite(value):  # pragma: no cover - callers gate on _finite first
        raise ValueError(f"xs:decimal cannot represent {value!r}")
    text = f"{value:.9f}".rstrip("0")
    return text + "0" if text.endswith(".") else text


def _finite(value: float | None) -> bool:
    """Whether a number is present and expressible as an ``xs:decimal``."""
    return value is not None and isfinite(value)


def _sub(parent: ET.Element, tag: str, text: str | None = None, **attrs: str) -> ET.Element:
    child = ET.SubElement(parent, tag, dict(attrs))
    if text is not None:
        child.text = text
    return child


def _numeric_requirement(entry: ScorecardEntry) -> tuple[float, float | None] | None:
    """The check's requirement as a QIF limit pair, or ``None`` if it has no numeric one.

    A QIF numeric nominal needs a target and at least one limit. That needs a required
    minimum that is a real, positive number: an absent one (a verdict-only check), a
    non-finite one (the NaN cases the scorecard already reports as not-evaluated), or a
    non-positive one (which passes every check and which
    :meth:`ScorecardEntry.from_safety_factor` refuses at construction) cannot be written
    as a limit. Those checks cross as attribute characteristics instead, which is the
    honest shape: a verdict with no fabricated nominal under it. The upper bound is
    dropped rather than fabricated when it is not a usable number.
    """
    required = entry.required_safety_factor
    if not _finite(required) or required <= 0:  # type: ignore[operator]
        return None
    upper = entry.upper_safety_factor
    if not _finite(upper) or upper <= required:  # type: ignore[operator]
        return float(required), None  # type: ignore[arg-type]
    return float(required), float(upper)  # type: ignore[arg-type]


def _description(entry: ScorecardEntry, layer: str) -> str:
    """The characteristic's Description: which layer, the detail line, and the caveats.

    Anything the QIF enumerations cannot carry lands here rather than being lost — the
    over-margin finding, the repair hint on a failing check, and a fragility warning from
    an attached margin distribution.
    """
    parts = [f"{layer}: {entry.detail}"]
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
    upper: float | None,
) -> str:
    nominal_id = ids.take()
    nominal = _sub(parent, "UserDefinedUnitCharacteristicNominal", id=nominal_id)
    _sub(nominal, "CharacteristicDefinitionId", definition_id)
    _sub(nominal, "Name", name)
    # The target is the required minimum: the smallest factor the spec accepts is the
    # value the design is aimed at. Stating the upper band as the target instead would
    # report every compliant part as under-target.
    _sub(nominal, "TargetValue", _decimal(required), unitName=SAFETY_FACTOR_UNIT)
    # The schema's choice: MaxValue (optionally followed by MinValue), or MinValue alone.
    # Element order is the schema's, not ours — a MinValue written before a MaxValue is
    # a different branch of the choice and does not validate.
    if upper is not None:
        _sub(nominal, "MaxValue", _decimal(upper), unitName=SAFETY_FACTOR_UNIT)
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

    for entry, layer in entries:
        limits = _numeric_requirement(entry)
        numeric = limits is not None
        definition_id = ids.take()
        if numeric:
            definition = _sub(
                definitions, "UserDefinedUnitCharacteristicDefinition", id=definition_id
            )
            _sub(definition, "Description", _description(entry, layer))
            _sub(definition, "Name", entry.name)
        else:
            definition = _sub(
                definitions, "UserDefinedAttributeCharacteristicDefinition", id=definition_id
            )
            _sub(definition, "Description", _description(entry, layer))
            _sub(definition, "Name", entry.name)
            # WhatToMeasure follows the base type's elements in the schema sequence.
            _sub(definition, "WhatToMeasure", entry.reference or entry.name)

        if numeric:
            required, upper = limits  # type: ignore[misc]
            nominal_id = _numeric_nominal(
                nominals,
                ids,
                definition_id=definition_id,
                name=entry.name,
                required=required,
                upper=upper,
            )
            item_tag = "UserDefinedUnitCharacteristicItem"
        else:
            nominal_id = _attribute_nominal(
                nominals, ids, definition_id=definition_id, name=entry.name
            )
            item_tag = "UserDefinedAttributeCharacteristicItem"

        item_id = ids.take()
        item = _sub(items, item_tag, id=item_id)
        if entry.reference:
            _sub(item, "Description", f"cites {entry.reference}")
        _sub(item, "Name", entry.name)
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


def _document_uuid(part_name: str, spec_digest: str, summary: str) -> str:
    """A deterministic document UUID, derived from the content it identifies.

    QIF requires a UUID on every document. Generating a random one would make two exports
    of the same evidence differ byte for byte, destroying exactly the property the
    attestation layer spends its effort preserving — so this is a digest of the
    identifying content, laid out in UUID form.

    The version nibble is 8 (RFC 9562's custom form) and not 5, because 5 would claim the
    value came from the SHA-1 namespace scheme and it did not. The variant bits are set so
    the value is a well-formed UUID rather than 32 hex characters wearing hyphens.
    """
    seed = f"urn:anvilate:qif:{part_name}:{spec_digest}:{summary}"
    digest = bytearray(sha256(seed.encode()).digest()[:16])
    digest[6] = (digest[6] & 0x0F) | 0x80  # version 8: custom, derived by this scheme
    digest[8] = (digest[8] & 0x3F) | 0x80  # RFC 9562 variant
    hexed = digest.hex()
    return f"{hexed[:8]}-{hexed[8:12]}-{hexed[12:16]}-{hexed[16:20]}-{hexed[20:]}"


def export_qif_results(
    sections: BundleSections,
    *,
    part_name: str,
    spec_digest: str,
    bom: EnvironmentBOM,
) -> str:
    """Export an evidence bundle's checks as a QIF Results document (ISO 23952).

    Every check in the bundle becomes a QIF characteristic: the analysis scorecard first,
    then the typed-callout scorecard when the bundle carries callouts, each tagged in its
    ``Description`` with the layer it came from. Nothing is filtered — a check that could
    not run crosses as a ``NOT_ANALYZED`` characteristic with no value, so a reader
    enumerating the file sees the same gaps the scorecard reports.

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
    _sub(root, "QPId", _document_uuid(part_name, spec_digest, summary))

    header = _sub(root, "Header")
    application = _sub(header, "Application")
    _sub(application, "Name", bom.application.name)
    _sub(application, "Organization", "Anvilate")
    _sub(
        header,
        "Description",
        f"Analytical screening evidence for {part_name} (spec digest {spec_digest}). {summary}",
    )
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
    return ET.tostring(root, encoding="unicode", xml_declaration=True) + "\n"


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


def qif_schema_issues(document: str) -> list[str]:
    """Structural problems in an emitted QIF document, as a list of complaints.

    The checks that do not need the schema package: the root element and namespace, the
    ``idMax`` claim against the ids actually present, uniqueness of those ids, every
    ``n`` count against the children it counts, and every internal reference resolving to
    an id in the file. An empty list means the document is self-consistent — not that it
    is schema-valid, which requires the published XSDs and an XSD-capable parser.
    """
    issues: list[str] = []
    root = ET.fromstring(document)
    if root.tag != f"{{{QIF_NAMESPACE}}}QIFDocument":
        issues.append(f"root element is {root.tag!r}, not a QIF document")
        return issues

    ids: list[str] = []
    for element in root.iter():
        identifier = element.get("id")
        if identifier is not None:
            ids.append(identifier)
    if len(set(ids)) != len(ids):
        issues.append("the document reuses a QIF id; ids must be unique across the file")
    declared = int(root.get("idMax", "0"))
    numeric = [int(i) for i in ids if i.isdigit()]
    if numeric and max(numeric) > declared:
        issues.append(f"idMax is {declared} but the document uses id {max(numeric)}")

    for element in root.iter():
        count = element.get("n")
        if count is None:
            continue
        if int(count) != len(element):
            issues.append(
                f"{_local(element.tag)} declares n={count} but carries {len(element)} children"
            )

    known = set(ids)
    for element in root.iter():
        tag = _local(element.tag)
        # QPId is the document's own UUID, not a reference to an id in the file. It ends
        # in "Id" and so was caught by the reference sweep, which reported every valid
        # document as broken.
        if tag.endswith("Id") and not tag.endswith("QPId") and element.text:
            if element.text.strip() not in known:
                issues.append(
                    f"{tag} references id {element.text.strip()!r}, which is not in the document"
                )
    return issues


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]
