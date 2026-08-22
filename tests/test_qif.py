"""Tests for the QIF Results export (ISO 23952 / ANSI QIF 3.0).

Two things are being pinned here. First, the mapping: every check crosses, with its
requirement, its actual, and its status, and a check that could not run crosses as a
characteristic that says so rather than vanishing. Second, the document itself: it is
self-consistent, it is deterministic, and — when the published schema package is pointed
at the suite — it validates.

The round trip is done through QIF's own structure, not through the writer's memory of
what it wrote: the reader walks Characteristics → Items → Measurements by
``CharacteristicItemId``, the way a quality package reading the file would, and
reconstructs the verdicts from there.
"""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest

from anvilate.attestation import Component, ComponentKind, EnvironmentBOM
from anvilate.bundle import BundleSections
from anvilate.evidence import SourceRecord
from anvilate.export.qif import (
    QIF_NAMESPACE,
    SAFETY_FACTOR_UNIT,
    export_qif_results,
    qif_schema_issues,
)
from anvilate.scorecard import CheckStatus, Direction, RepairHint, Scorecard, ScorecardEntry
from anvilate.uncertainty import Symmetric

_NS = {"q": QIF_NAMESPACE}


def _bom() -> EnvironmentBOM:
    return EnvironmentBOM(
        application=Component(name="anvilate", version="0.0.1", kind=ComponentKind.APPLICATION),
        components=(
            Component(name="pint", version="0.24"),
            Component(name="materials-db", version="2026.08", kind=ComponentKind.DATA),
        ),
    )


def _card() -> Scorecard:
    """One of each shape the mapping has to handle."""
    return Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor("bearing stress", computed=2.4, required=2.0),
            ScorecardEntry.from_safety_factor(
                "net section",
                computed=1.2,
                required=2.0,
                repair_hint=RepairHint.directional("thickness", direction=Direction.INCREASE),
            ),
            ScorecardEntry.from_safety_factor("weld shear", computed=9.0, required=2.0, upper=4.0),
            ScorecardEntry.from_safety_factor("plate tear-out", computed=None, required=2.0),
            ScorecardEntry(
                name="deflection",
                status=CheckStatus.PASS,
                detail="L/360 met",
                reference="AISC 360-22 L3",
            ),
        )
    )


def _sections(card: Scorecard | None = None) -> BundleSections:
    return BundleSections(
        scorecard=card if card is not None else _card(),
        citations=(
            SourceRecord(
                ref="A36",
                kind="material",
                name="ASTM A36",
                sources=("ASTM A36 specified minimum (specification minimum)",),
            ),
            SourceRecord(
                ref="general_tolerance",
                kind="tolerance",
                name="ISO 2768-m",
                sources=("ISO 2768-1 general tolerances",),
            ),
        ),
    )


def _export(sections: BundleSections | None = None) -> str:
    return export_qif_results(
        sections if sections is not None else _sections(),
        part_name="lug-01",
        spec_digest="sha256:abc123",
        bom=_bom(),
    )


def _read_characteristics(document: str) -> dict[str, dict[str, object]]:
    """Read a QIF Results document the way a quality package would.

    Walks the characteristic items, follows each to its nominal (for the requirement) and
    from the measurements back by ``CharacteristicItemId`` (for the actual and status),
    keyed by characteristic name. Nothing here knows what the writer intended — only what
    QIF says these elements mean.
    """
    root = ET.fromstring(document)
    nominals = {
        nominal.get("id"): nominal
        for nominal in root.findall("./q:Characteristics/q:CharacteristicNominals/*", _NS)
    }
    by_item: dict[str, dict[str, object]] = {}
    for item in root.findall("./q:Characteristics/q:CharacteristicItems/*", _NS):
        nominal = nominals[item.findtext("q:CharacteristicNominalId", namespaces=_NS)]
        minimum = nominal.findtext("q:MinValue", namespaces=_NS)
        maximum = nominal.findtext("q:MaxValue", namespaces=_NS)
        by_item[item.get("id")] = {
            "name": item.findtext("q:Name", namespaces=_NS),
            "required": None if minimum is None else float(minimum),
            "upper": None if maximum is None else float(maximum),
            "attribute": "Attribute" in nominal.tag,
        }

    found: dict[str, dict[str, object]] = {}
    measurements = root.findall(
        "./q:Results/q:MeasurementResultsSet/q:MeasurementResults"
        "/q:MeasuredCharacteristics/q:CharacteristicMeasurements/*",
        _NS,
    )
    # The reader keys by name, which is what a quality package does — and which is exactly
    # how a lost characteristic becomes invisible to the tests that exist to catch the loss.
    # Refusing a collapse here means every test built on this reader sees one.
    assert len(measurements) == len(by_item), (
        f"{len(by_item)} characteristic items but {len(measurements)} measurements"
    )
    for measurement in measurements:
        record = dict(by_item[measurement.findtext("q:CharacteristicItemId", namespaces=_NS)])
        record["status"] = measurement.findtext(
            "q:Status/q:CharacteristicStatusEnum", namespaces=_NS
        )
        value = measurement.find("q:Value", _NS)
        record["value"] = None if value is None else value.text
        record["unit"] = None if value is None else value.get("unitName")
        record["description"] = measurement.findtext("q:Description", namespaces=_NS)
        found[record["name"]] = record  # type: ignore[index]
    assert len(found) == len(measurements), (
        "two characteristics share a name, so reading by name lost one of them"
    )
    return found


def test_every_check_crosses_as_a_characteristic():
    read = _read_characteristics(_export())
    assert set(read) == {
        "bearing stress",
        "net section",
        "weld shear",
        "plate tear-out",
        "deflection",
    }


def test_requirement_actual_and_status_survive_the_round_trip():
    read = _read_characteristics(_export())
    bearing = read["bearing stress"]
    assert bearing["status"] == "PASS"
    assert bearing["required"] == 2.0
    assert float(bearing["value"]) == pytest.approx(2.4)  # type: ignore[arg-type]
    assert bearing["unit"] == SAFETY_FACTOR_UNIT

    failing = read["net section"]
    assert failing["status"] == "FAIL"
    assert float(failing["value"]) == pytest.approx(1.2)  # type: ignore[arg-type]
    # The repair hint has no QIF slot; it crosses in the description rather than dying.
    assert "increase thickness" in failing["description"]  # type: ignore[operator]


def test_not_evaluated_survives_the_mapping():
    """The no-silent-green property has to be a property of the interchange file too."""
    read = _read_characteristics(_export())
    gap = read["plate tear-out"]
    assert gap["status"] == "NOT_ANALYZED"
    # Present, named, requirement stated — and carrying no actual, because there is none.
    assert gap["required"] == 2.0
    assert gap["value"] is None
    assert "not evaluated" in gap["description"]  # type: ignore[operator]


def test_over_margin_passes_but_says_so():
    """QIF has no 'passed too well'. It maps to PASS with the finding stated."""
    read = _read_characteristics(_export())
    over = read["weld shear"]
    assert over["status"] == "PASS"
    assert over["required"] == 2.0
    assert "over-margin" in over["description"]  # type: ignore[operator]


def test_the_over_engineering_band_is_not_written_as_a_tolerance_limit():
    """In QIF a MaxValue is a conformance limit and a value past it is nonconforming. In
    Anvilate the upper band is an over-engineering flag that never blocks anything. Writing
    one as the other produced a document whose own numbers said out-of-tolerance next to a
    status that said PASS, and a reader recomputing conformance would have rejected a part
    the doctrine calls fine."""
    read = _read_characteristics(_export())
    assert read["weld shear"]["upper"] is None
    # It is not lost — it is stated where it cannot be mistaken for a limit.
    assert "target band" in read["weld shear"]["description"]  # type: ignore[operator]
    assert "not a conformance limit" in read["weld shear"]["description"]  # type: ignore[operator]


def test_a_verdict_only_check_becomes_an_attribute_characteristic():
    """No numeric requirement means no invented nominal — QIF's attribute gauge instead."""
    read = _read_characteristics(_export())
    verdict = read["deflection"]
    assert verdict["attribute"] is True
    assert verdict["required"] is None
    assert verdict["value"] == "pass"


def test_attribute_nominal_declares_its_pass_and_fail_values():
    root = ET.fromstring(_export())
    nominal = root.find(
        "./q:Characteristics/q:CharacteristicNominals/q:UserDefinedAttributeCharacteristicNominal",
        _NS,
    )
    assert nominal is not None
    assert nominal.findtext("q:PassValues/q:StringValue", namespaces=_NS) == "pass"
    assert nominal.findtext("q:FailValues/q:StringValue", namespaces=_NS) == "fail"


def test_traceability_names_the_spec_revision_and_the_toolchain():
    root = ET.fromstring(_export())
    description = root.findtext("./q:Header/q:Description", namespaces=_NS)
    assert "lug-01" in description
    assert "sha256:abc123" in description
    software = {
        entry.findtext("q:ApplicationName", namespaces=_NS): entry.findtext(
            "q:Version", namespaces=_NS
        )
        for entry in root.findall("./q:SoftwareDefinitions/q:Software", _NS)
    }
    assert software == {"anvilate": "0.0.1", "pint": "0.24", "materials-db": "2026.08"}


def test_the_scope_line_refuses_to_read_as_a_certified_inspection():
    root = ET.fromstring(_export())
    scope = root.findtext("./q:Header/q:Scope", namespaces=_NS)
    assert "not a certified analysis" in scope
    assert "NOT_ANALYZED" in scope


def test_citations_become_standards_with_the_right_organization():
    root = ET.fromstring(_export())
    standards = root.findall("./q:StandardsDefinitions/q:Standard", _NS)
    designators = [s.findtext("q:Designator", namespaces=_NS) for s in standards]
    assert designators == ["ISO 23952", "ASTM A36", "ISO 2768-m"]
    # ISO is one of the bodies QIF enumerates; ASTM is not, so it takes the "other" branch.
    assert (
        standards[0].findtext("q:Organization/q:StandardsOrganizationEnum", namespaces=_NS) == "ISO"
    )
    assert (
        standards[1].findtext("q:Organization/q:OtherStandardsOrganization", namespaces=_NS)
        is not None
    )


def test_the_document_status_rolls_up_at_the_bundles_precedence():
    root = ET.fromstring(_export())
    status = root.findtext(
        "./q:Results/q:MeasurementResultsSet/q:MeasurementResults"
        "/q:InspectionStatus/q:InspectionStatusEnum",
        namespaces=_NS,
    )
    # The card has a failing check, so the document says FAIL — not the majority verdict.
    assert status == "FAIL"


def test_a_card_that_only_has_gaps_reports_not_calculated():
    """The InspectionStatus enumeration spells this differently from the characteristic
    one (NOT_CALCULATED, not NOT_ANALYZED); mapping one from the other by string would
    have emitted an invalid document."""
    card = Scorecard(
        entries=(ScorecardEntry.from_safety_factor("shear", computed=None, required=2.0),)
    )
    root = ET.fromstring(_export(_sections(card)))
    assert (
        root.findtext(
            "./q:Results/q:MeasurementResultsSet/q:MeasurementResults"
            "/q:InspectionStatus/q:InspectionStatusEnum",
            namespaces=_NS,
        )
        == "NOT_CALCULATED"
    )


def test_the_callout_layer_crosses_too():
    """A layer of verdicts dropped from the interchange file is a silent green."""
    from anvilate.callouts import CalloutSet, HeatTreatment

    sections = BundleSections(
        scorecard=_card(),
        callouts=CalloutSet(
            callouts=(
                HeatTreatment(specification="AMS 2759/1", condition="QT", hardness="38-42 HRC"),
            )
        ),
    )
    read = _read_characteristics(
        export_qif_results(sections, part_name="lug-01", spec_digest="sha256:abc123", bom=_bom())
    )
    layers = {record["description"].split(":", 1)[0] for record in read.values()}  # type: ignore[union-attr]
    assert layers == {"analysis", "callouts"}
    assert len(read) > len(_card().entries)


def test_the_export_is_deterministic():
    """Two exports of the same evidence are byte-identical — the property the content
    address depends on, and the one a random document UUID would have destroyed."""
    assert _export() == _export()


def test_a_different_spec_digest_is_a_different_document():
    other = export_qif_results(
        _sections(), part_name="lug-01", spec_digest="sha256:def456", bom=_bom()
    )
    assert other != _export()


def test_the_emitted_document_is_self_consistent():
    assert qif_schema_issues(_export()) == []


def test_the_self_check_catches_a_broken_reference():
    broken = _export().replace("<CharacteristicItemId>", "<CharacteristicItemId>9", 1)
    issues = qif_schema_issues(broken)
    assert any("references id" in issue for issue in issues)


def test_the_self_check_catches_a_miscounted_list():
    broken = _export().replace('<SoftwareDefinitions n="3">', '<SoftwareDefinitions n="7">', 1)
    issues = qif_schema_issues(broken)
    assert any("declares n=7" in issue for issue in issues)


def test_the_self_check_catches_an_understated_idmax():
    broken = _export().replace('idMax="', 'idMax="0" oldIdMax="', 1)
    issues = qif_schema_issues(broken)
    assert any("idMax is 0" in issue for issue in issues)


@pytest.mark.parametrize(
    ("part_name", "spec_digest"),
    [("", "sha256:abc"), ("   ", "sha256:abc"), ("lug", ""), ("lug", "  ")],
)
def test_the_export_refuses_to_be_anonymous(part_name, spec_digest):
    # With no `match=`, any ValueError satisfied all four cases — including one raised for
    # a completely different reason.
    expected = "part it is about" if not part_name.strip() else "digest of the spec revision"
    with pytest.raises(ValueError, match=expected):
        export_qif_results(_sections(), part_name=part_name, spec_digest=spec_digest, bom=_bom())


def test_no_value_is_written_in_exponent_notation():
    """``xs:decimal`` has no exponent form, so a very small or very large safety factor
    written through ``repr`` would be an invalid document that only shows up on the
    reader's side."""
    card = Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor("tiny", computed=1.5e-7, required=1e-8),
            ScorecardEntry.from_safety_factor("huge", computed=4.2e6, required=2.0),
        )
    )
    document = _export(_sections(card))
    assert "e-" not in document.lower().split("<characteristics")[1]
    read = _read_characteristics(document)
    assert float(read["huge"]["value"]) == pytest.approx(4.2e6)  # type: ignore[arg-type]


def test_a_non_finite_actual_leaves_the_value_out_rather_than_lying():
    """An infinite safety factor (zero demand) has no ``xs:decimal`` spelling. The
    characteristic still exists and still carries its status; it simply reports no
    number, which is true."""
    card = Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor("no demand", computed=float("inf"), required=2.0),
        )
    )
    read = _read_characteristics(_export(_sections(card)))
    assert read["no demand"]["status"] == "PASS"
    assert read["no demand"]["value"] is None


@pytest.mark.parametrize("required", [0.0, -1.0, float("nan")])
def test_an_unusable_requirement_falls_back_to_a_verdict_not_a_fake_limit(required):
    """A requirement that cannot be a QIF limit must not become one anyway. The check
    crosses as an attribute characteristic — a verdict with no fabricated nominal."""
    card = Scorecard(
        entries=(
            ScorecardEntry(
                name="odd",
                status=CheckStatus.PASS,
                detail="constructed directly",
                safety_factor=3.0,
                required_safety_factor=required,
            ),
        )
    )
    read = _read_characteristics(_export(_sections(card)))
    assert read["odd"]["attribute"] is True
    assert read["odd"]["required"] is None


def test_an_upper_band_at_or_below_the_minimum_is_dropped_not_emitted():
    """QIF's nominal has no room for a max below its min, and emitting one produces a
    document that reads as a requirement no part can meet."""
    card = Scorecard(
        entries=(
            ScorecardEntry(
                name="inverted band",
                status=CheckStatus.PASS,
                detail="constructed directly",
                safety_factor=3.0,
                required_safety_factor=2.0,
                upper_safety_factor=1.0,
            ),
        )
    )
    read = _read_characteristics(_export(_sections(card)))
    assert read["inverted band"]["required"] == 2.0
    assert read["inverted band"]["upper"] is None


def test_the_document_validates_against_the_published_schemas():
    """The real conformance check, opt-in because the schemas are a separate download.

    Point ``ANVILATE_QIF_XSD`` at the ``xsd`` directory of the QIF 3.0 schema package
    (free, https://qifstandards.org/download/) with ``lxml`` installed and this validates
    an emitted document against ``QIFApplications/QIFDocument.xsd``. Skipped otherwise —
    an unrunnable check is reported as not run, never as a pass.
    """
    etree = pytest.importorskip("lxml.etree")
    location = os.environ.get("ANVILATE_QIF_XSD")
    if not location:
        pytest.skip("set ANVILATE_QIF_XSD to the QIF 3.0 schema package's xsd directory")
    schema_file = Path(location) / "QIFApplications" / "QIFDocument.xsd"
    if not schema_file.exists():
        pytest.skip(f"no QIFDocument.xsd under {location}")
    schema = etree.XMLSchema(etree.parse(str(schema_file)))
    document = etree.fromstring(_export().encode("utf-8"))
    assert schema.validate(document), "\n".join(str(e) for e in schema.error_log)


# --- what a five-agent audit found the day this module shipped --------------------------
#
# Every test below is a defect that was live in the first commit of this module. Two of them
# emitted a schema-valid document that a conformant reader would have read as passing.


def test_two_checks_with_one_name_stay_two_characteristics():
    """`screen_structure` merges every member into one card, so two beams both contribute
    "B1 bending" — and a reader keying by characteristic name, which is what quality
    software joins on, kept whichever came last. An overstressed member read as passing."""
    card = Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor("bending", computed=1.17, required=1.5),
            ScorecardEntry.from_safety_factor("bending", computed=46.9, required=1.5),
        )
    )
    read = _read_characteristics(_export(_sections(card)))
    assert len(read) == 2
    assert set(read) == {"bending", "bending #2"}
    assert read["bending"]["status"] == "FAIL"
    assert read["bending #2"]["status"] == "PASS"


def test_an_unnamed_check_still_gets_a_key():
    card = Scorecard(entries=(ScorecardEntry(name="   ", status=CheckStatus.PASS, detail="x"),))
    assert "unnamed check" in _read_characteristics(_export(_sections(card)))


def test_a_failing_factor_is_not_rounded_up_onto_its_own_limit():
    """Nine-decimal formatting rounded 1.9999999996 to "2.0" — exactly its own MinValue —
    so a reader recomputing conformance from the limits called a FAIL conforming."""
    card = Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor("interaction", computed=1.9999999996, required=2.0),
        )
    )
    read = _read_characteristics(_export(_sections(card)))
    assert read["interaction"]["status"] == "FAIL"
    assert float(read["interaction"]["value"]) < read["interaction"]["required"]  # type: ignore[arg-type,operator]


def test_a_tiny_requirement_is_not_written_as_a_limit_everything_meets():
    """A positive requirement of 1e-12 came out as `MinValue 0.0` — a limit every value on
    earth satisfies, which is the precise thing both `_numeric_requirement` and
    `from_safety_factor` refuse at the front door."""
    card = Scorecard(
        entries=(ScorecardEntry.from_safety_factor("tiny", computed=2e-12, required=1e-12),)
    )
    read = _read_characteristics(_export(_sections(card)))
    # Scaled, because approx's default abs=1e-12 would swamp a rel= at this magnitude and
    # the assertion would degenerate to "the answer is small" — which is the bug.
    assert read["tiny"]["required"] * 1e12 == pytest.approx(1.0)  # type: ignore[operator]
    assert read["tiny"]["required"] > 0.0  # type: ignore[operator]
    assert float(read["tiny"]["value"]) * 1e12 == pytest.approx(2.0)  # type: ignore[arg-type]


def test_a_failing_verdict_only_check_reads_back_as_fail():
    """The attribute characteristic's FAIL value was never exercised: every attribute entry
    in the fixture passed, so `_PASS_VALUE if entry.passed else _FAIL_VALUE` could have been
    written without its else half and nothing would have gone red."""
    card = Scorecard(
        entries=(
            ScorecardEntry(name="tip deflection", status=CheckStatus.FAIL, detail="L/240 only"),
        )
    )
    read = _read_characteristics(_export(_sections(card)))
    assert read["tip deflection"]["attribute"] is True
    assert read["tip deflection"]["status"] == "FAIL"
    assert read["tip deflection"]["value"] == "fail"


def test_a_control_character_does_not_produce_a_document_nobody_can_open():
    """A check name carrying a character XML cannot represent produced a document no parser
    would accept — and `qif_schema_issues` raised on it rather than reporting it, so the
    failure surfaced at the reader instead of at the writer."""
    card = Scorecard(
        entries=(ScorecardEntry(name="bolt\x0bshear", status=CheckStatus.PASS, detail="ok"),)
    )
    document = _export(_sections(card))
    assert qif_schema_issues(document) == []
    assert len(_read_characteristics(document)) == 1


def test_the_self_check_reports_an_unparseable_document_instead_of_raising():
    issues = qif_schema_issues("<QIFDocument><unclosed>")
    assert issues and "not well-formed" in issues[0]


def test_the_self_check_catches_an_overstated_idmax():
    """The one-sided version passed a document claiming 999 ids while carrying 27."""
    broken = _export().replace('idMax="', 'idMax="999" oldIdMax="', 1)
    assert any("idMax is 999" in issue for issue in qif_schema_issues(broken))


def test_the_self_check_catches_a_reference_pointing_at_the_wrong_kind_of_thing():
    """Checking only that a reference resolves to *some* id let a CharacteristicItemId point
    at a Software entry and pass clean, silently orphaning a verdict."""
    document = _export()
    root = ET.fromstring(document)
    software_id = root.find("./q:SoftwareDefinitions/q:Software", _NS).get("id")
    original = root.find(
        "./q:Results/q:MeasurementResultsSet/q:MeasurementResults"
        "/q:MeasuredCharacteristics/q:CharacteristicMeasurements/*/q:CharacteristicItemId",
        _NS,
    ).text
    broken = document.replace(
        f"<CharacteristicItemId>{original}</CharacteristicItemId>",
        f"<CharacteristicItemId>{software_id}</CharacteristicItemId>",
        1,
    )
    assert any("is a Software and not a" in issue for issue in qif_schema_issues(broken))


def test_the_qpid_moves_when_anything_in_the_document_moves():
    """Seeding the identifier on the part name, the spec digest and the bundle's one-line
    summary looked equivalent to seeding it on the content and was not: two bundles
    differing in every safety factor, every citation and every BOM entry produced
    byte-different documents under one identifier — and the QPId is the key a QIF archive
    stores them under."""
    other_bom = EnvironmentBOM(
        application=Component(name="anvilate", version="9.9.9", kind=ComponentKind.APPLICATION)
    )
    variants = [
        _export(),
        export_qif_results(
            _sections(), part_name="lug-01", spec_digest="sha256:abc123", bom=other_bom
        ),
        _export(
            BundleSections(
                scorecard=Scorecard(
                    entries=(
                        ScorecardEntry.from_safety_factor(
                            "bearing stress", computed=2.5, required=2.0
                        ),
                    )
                )
            )
        ),
    ]
    identifiers = [
        ET.fromstring(document).findtext("q:QPId", namespaces=_NS) for document in variants
    ]
    assert len(set(identifiers)) == len(identifiers)
    # And it is still deterministic: the same evidence keeps the same identifier.
    assert identifiers[0] == ET.fromstring(_export()).findtext("q:QPId", namespaces=_NS)


def test_a_failed_physical_test_is_in_the_characteristic_list():
    """The worst document this exporter could produce: a lifter whose proof test cracked it
    at 108% exported one PASS characteristic and a document-level FAIL, with the words
    "cracked" and "proof load" nowhere in the file. A reader recomputing the roll-up from
    the characteristics got PASS."""
    from anvilate.verification import (
        VerificationArchetype,
        VerificationItem,
        VerificationMethod,
        VerificationOutcome,
        VerificationPlan,
    )

    archetype = VerificationArchetype(
        key="proof-load",
        method=VerificationMethod.TEST,
        title="Proof load test",
        clause_token="ASME BTH-1",
        acceptance_template="no permanent deformation at 125% of rated load",
        citation="ASME B30.20",
    )
    plan = VerificationPlan(
        items=(
            VerificationItem(
                name="proof load to 125%",
                archetype=archetype,
                driving_checks=("pin bearing",),
                acceptance="no permanent deformation",
                outcome=VerificationOutcome(
                    passed=False,
                    measured="lug cracked at 108% of rated load",
                    instrument="load frame LF-2",
                    performed_by="A. Technician",
                    performed_on=date(2026, 5, 4),
                ),
            ),
        ),
        analysis_only=(),
        unresolved=(("plate tear-out", "no dimension for the tear-out path"),),
    )
    sections = BundleSections(
        scorecard=Scorecard(
            entries=(ScorecardEntry.from_safety_factor("pin bearing", computed=2.7, required=2.0),)
        ),
        verification=plan,
    )
    read = _read_characteristics(_export(sections))
    assert "proof load to 125%" in read
    assert read["proof load to 125%"]["status"] == "FAIL"
    assert "cracked at 108%" in read["proof load to 125%"]["description"]  # type: ignore[operator]
    # And the coverage it could not resolve crosses as a gap rather than as an absence.
    assert read["verification coverage: plate tear-out"]["status"] == "NOT_ANALYZED"
    # A reader recomputing the roll-up from the characteristics now reaches the same verdict
    # the document states.
    assert any(record["status"] == "FAIL" for record in read.values())


def test_the_header_discloses_the_layers_that_are_not_characteristics():
    """The scope claim rested on one un-asserted f-string interpolation: dropping the
    bundle summary from the header left the document mentioning the uncovered layers
    nowhere, and the whole suite stayed green."""
    description = ET.fromstring(_export()).findtext("./q:Header/q:Description", namespaces=_NS)
    summary = _sections().summary()
    assert summary in description
    assert "not covered" in description


# --- survivors a mutation pass left standing ---------------------------------------------
#
# Each of these is a line the suite executed and never asserted. They are ordered by how bad
# the undetected drift would be, and every one was demonstrated by mutating the source and
# watching the whole suite stay green.


def test_an_over_margin_bundle_exports_a_passing_document_status():
    """`_INSPECTION_STATUS[OVER_MARGIN] = "PASS"` is an explicit design position stated in
    the module docstring, and nothing tested it at the document level: flipping it to FAIL
    made quality software reject a conforming part, silently."""
    card = Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor("weld shear", computed=9.0, required=2.0, upper=4.0),
        )
    )
    sections = _sections(card)
    assert sections.status is CheckStatus.OVER_MARGIN
    status = ET.fromstring(_export(sections)).findtext(
        "./q:Results/q:MeasurementResultsSet/q:MeasurementResults"
        "/q:InspectionStatus/q:InspectionStatusEnum",
        namespaces=_NS,
    )
    assert status == "PASS"


def test_the_numeric_nominal_declares_its_values_as_limits():
    """`DefinedAsLimit` is the difference between "MinValue 2.0 is a lower limit" and
    "MinValue 2.0 is a deviation from a target of 2.0", i.e. an acceptance band of 0 to 4.
    Every numeric characteristic in the file changes meaning and no test saw it."""
    nominal = ET.fromstring(_export()).find(
        "./q:Characteristics/q:CharacteristicNominals/q:UserDefinedUnitCharacteristicNominal",
        _NS,
    )
    assert nominal.findtext("q:DefinedAsLimit", namespaces=_NS) == "true"


def test_the_numeric_nominals_children_are_in_the_schemas_own_order():
    """The nominal's content model is a sequence with a choice in it; a member written out
    of order is a document that does not validate, and `qif_schema_issues` checks ids,
    counts and references — not sequence order."""
    nominal = ET.fromstring(_export()).find(
        "./q:Characteristics/q:CharacteristicNominals/q:UserDefinedUnitCharacteristicNominal",
        _NS,
    )
    assert [child.tag.rsplit("}", 1)[-1] for child in nominal] == [
        "CharacteristicDefinitionId",
        "Name",
        "TargetValue",
        "MinValue",
        "DefinedAsLimit",
    ]


def test_the_target_value_is_the_required_minimum_not_the_band_top():
    """The code comment states the failure verbatim: stating the upper band as the target
    would report every compliant part as under-target."""
    nominal = ET.fromstring(_export()).find(
        "./q:Characteristics/q:CharacteristicNominals/q:UserDefinedUnitCharacteristicNominal",
        _NS,
    )
    target = nominal.findtext("q:TargetValue", namespaces=_NS)
    assert float(target) == pytest.approx(2.0)
    assert target == nominal.findtext("q:MinValue", namespaces=_NS)


def test_the_document_identifier_is_a_well_formed_uuid_that_claims_what_it_is():
    """The docstring makes an explicit correctness claim — version 8, RFC 9562's custom
    form, and not version 5, which would say the value came from the SHA-1 namespace scheme
    it did not come from. One assertion pins both nibbles and well-formedness."""
    from uuid import UUID

    identifier = UUID(ET.fromstring(_export()).findtext("q:QPId", namespaces=_NS))
    assert identifier.version == 8
    assert identifier.variant is not None
    assert str(identifier) == ET.fromstring(_export()).findtext("q:QPId", namespaces=_NS)


def test_a_not_evaluated_check_carrying_a_number_still_exports_no_value():
    """A NOT_EVALUATED entry *can* carry a finite safety factor — a NaN upper band produces
    exactly that. Without the `entry.evaluated` half of the gate, the characteristic
    exported as NOT_ANALYZED with a Value in it, and a reader consuming values rather than
    statuses picked up a number from a check that never ran."""
    entry = ScorecardEntry.from_safety_factor(
        "interaction", computed=2.0, required=1.5, upper=float("nan")
    )
    assert entry.status is CheckStatus.NOT_EVALUATED
    assert entry.safety_factor == pytest.approx(2.0)
    read = _read_characteristics(_export(_sections(Scorecard(entries=(entry,)))))
    assert read["interaction"]["status"] == "NOT_ANALYZED"
    assert read["interaction"]["value"] is None


def test_the_self_check_catches_a_duplicated_id():
    """The uniqueness check is the one structural gate on the emitted document that does not
    need the XSD package, and deleting its body left the suite green."""
    document = _export()
    broken = document.replace('<Standard id="2">', '<Standard id="1">', 1)
    assert any("reuses a QIF id" in issue for issue in qif_schema_issues(broken))


def test_a_hyphenated_citation_still_finds_its_standards_body():
    """ "ISO-286" is how the designator is commonly written, and the split-on-hyphen half of
    the detection had no fixture: without it, every hyphenated ISO citation falls out of the
    enumeration and a QIF consumer filtering by standards body stops seeing them."""
    sections = BundleSections(
        scorecard=_card(),
        citations=(
            SourceRecord(
                ref="fit", kind="tolerance", name="ISO-286 H7/h6", sources=("ISO-286-2 fits",)
            ),
        ),
    )
    standards = ET.fromstring(_export(sections)).findall("./q:StandardsDefinitions/q:Standard", _NS)
    assert (
        standards[1].findtext("q:Organization/q:StandardsOrganizationEnum", namespaces=_NS) == "ISO"
    )


def test_a_verdict_only_characteristic_says_what_it_was_measured_against():
    """`WhatToMeasure` is required by the schema and carries the clause reference — the only
    place a verdict-only characteristic says what it was judged against. Dropping the line
    entirely also left the suite green while the document stopped validating."""
    definition = ET.fromstring(_export()).find(
        "./q:Characteristics/q:CharacteristicDefinitions"
        "/q:UserDefinedAttributeCharacteristicDefinition",
        _NS,
    )
    assert definition.findtext("q:WhatToMeasure", namespaces=_NS) == "AISC 360-22 L3"


def test_a_small_value_keeps_its_digits_rather_than_flattening_to_zero():
    """A badly failing check is exactly the one whose number matters, and fixed-point
    formatting flattened it. One assertion pins both the notation and the precision."""
    from anvilate.export.qif import _decimal

    assert _decimal(1.234567e-05) == "0.00001234567"
    assert _decimal(4.2e6) == "4200000.0"
    assert "e" not in _decimal(1e-30).lower()


def test_the_declared_unit_is_the_one_every_value_references():
    """The declaration side of the unit was loose while the reference side was pinned: the
    `FileUnits` entry could be renamed and every `unitName=` would point at a unit the
    document does not define."""
    root = ET.fromstring(_export())
    declared = root.findtext(
        "./q:FileUnits/q:UserDefinedUnits/q:UserDefinedUnit/q:UnitName", namespaces=_NS
    )
    assert declared == SAFETY_FACTOR_UNIT
    referenced = {
        element.get("unitName") for element in root.iter() if element.get("unitName") is not None
    }
    assert referenced == {declared}, (
        f"values reference {referenced} but FileUnits declares only {declared!r}"
    )


# --- what a second audit wave found in the first wave's fixes ---------------------------


def test_disambiguating_a_name_does_not_create_the_collision_it_prevents():
    """The suffix was generated by counting and never checked against what had actually been
    emitted. A card carrying "bending", "bending" and "bending #2" — which is what a
    re-import of a previous Anvilate export looks like — produced "bending #2" twice, and one
    of the two was the FAIL."""
    from anvilate.export.qif import _unique_names

    for names in (
        ["bending", "bending", "bending #2"],
        ["b", "b #2", "b", "b"],
        ["x", "x", "x", "x #2", "x #3"],
        ["", "", "unnamed check"],
    ):
        unique = _unique_names(names)
        assert len(set(unique)) == len(unique), f"{names} -> {unique}"
        assert len(unique) == len(names)

    card = Scorecard(
        entries=(
            ScorecardEntry.from_safety_factor("bending", computed=2.4, required=1.5),
            ScorecardEntry.from_safety_factor("bending", computed=0.5, required=1.5),
            ScorecardEntry.from_safety_factor("bending #2", computed=3.0, required=1.5),
        )
    )
    read = _read_characteristics(_export(_sections(card)))
    assert len(read) == 3
    assert sum(1 for record in read.values() if record["status"] == "FAIL") == 1


def test_the_self_check_does_not_cry_wolf_about_free_text_that_ends_in_id():
    """Sweeping every element whose name ends in "Id" reported a schema-valid document as
    broken: `EmployeeId` is `xs:token` free text and lives in a MeasurementResults
    traceability block — inside the document class this exporter emits. A self-check that
    complains about the thing it is meant to certify gets switched off."""
    document = _export()
    root = ET.fromstring(document)
    results = root.find("./q:Results/q:MeasurementResultsSet/q:MeasurementResults", _NS)
    traceability = ET.SubElement(results, f"{{{QIF_NAMESPACE}}}InspectionTraceability")
    operator = ET.SubElement(traceability, f"{{{QIF_NAMESPACE}}}InspectionOperator")
    employee = ET.SubElement(operator, f"{{{QIF_NAMESPACE}}}EmployeeId")
    employee.text = "E-4471"
    with_traceability = ET.tostring(root, encoding="unicode")
    assert qif_schema_issues(with_traceability) == []


def test_a_verification_plan_that_carries_nothing_still_crosses_as_a_gap():
    """An empty plan produced no per-item entries at all, so the bundle's status went
    NOT_EVALUATED while the characteristic list held nothing but passes — a reader
    recomputing the roll-up from the characteristics got PASS, which is the same denial of a
    gap the per-item crossing was added to fix."""
    from anvilate.verification import VerificationPlan

    sections = BundleSections(
        scorecard=Scorecard(
            entries=(ScorecardEntry.from_safety_factor("pin bearing", computed=2.7, required=2.0),)
        ),
        verification=VerificationPlan(items=(), analysis_only=(), unresolved=()),
    )
    assert sections.status is CheckStatus.NOT_EVALUATED
    read = _read_characteristics(_export(sections))
    assert read["verification plan"]["status"] == "NOT_ANALYZED"
    # And a reader recomputing from the characteristics reaches the document's own verdict.
    assert any(record["status"] == "NOT_ANALYZED" for record in read.values())


@pytest.mark.parametrize("character", ["\x00", "\x08", "\x0b", "\x0c", "\x0e", "\x1f", "\x7f"])
def test_every_character_xml_cannot_carry_is_replaced(character):
    r"""One test pinned exactly one character. Dropping `\x0e-\x1f` from the pattern left the
    whole range free, and a check named "bolt\x1fshear" emitted a document no parser will
    open — which is the failure the replacement exists to prevent, for six of its seven
    characters."""
    card = Scorecard(
        entries=(
            ScorecardEntry(name=f"bolt{character}shear", status=CheckStatus.PASS, detail="ok"),
        )
    )
    document = _export(_sections(card))
    assert qif_schema_issues(document) == []
    read = _read_characteristics(document)
    # Replaced, not deleted. Dropping the character silently joins the words into a
    # different key, and a characteristic name is what quality software joins on.
    assert "bolt�shear" in read


@pytest.mark.parametrize("character", ["\t", "\n", "\r"])
def test_the_whitespace_xml_does_carry_is_left_alone(character):
    from anvilate.export.qif import _legal

    assert _legal(f"a{character}b") == f"a{character}b"


def test_two_records_citing_one_standard_produce_one_standard_entry():
    """The QIF standards list is meant to be a set of standards, not a set of lookups — a
    materials handbook behind both the plate and the bolt is one citation. Without the
    collapse the same standard is written several times under different ids."""
    shared = "ASTM A36 specified minimum (specification minimum)"
    sections = BundleSections(
        scorecard=_card(),
        citations=(
            SourceRecord(ref="plate", kind="material", name="ASTM A36", sources=(shared,)),
            SourceRecord(ref="bolt", kind="material", name="ASTM A36", sources=(shared,)),
        ),
    )
    standards = ET.fromstring(_export(sections)).findall("./q:StandardsDefinitions/q:Standard", _NS)
    # QIF itself, plus the one citation the two records share.
    assert len(standards) == 2
    assert qif_schema_issues(_export(sections)) == []


def test_a_fragile_check_carries_its_warning_across():
    """A nominal pass that the declared input scatter fails materially often crossed as a
    plain PASS with the caveat silently dropped, and the document then says PASS with nothing
    qualifying it."""
    from anvilate.uncertainty import sample_margin

    scatter = sample_margin(
        lambda values: values["load"],
        {"load": Symmetric(nominal=1.6, half_width=0.5, sigma_level=1.0)},
        required=1.5,
        seed=7,
    )
    assert scatter.is_fragile()
    entry = ScorecardEntry.from_safety_factor("bearing", computed=1.6, required=1.5).model_copy(
        update={"uncertainty": scatter}
    )
    read = _read_characteristics(_export(_sections(Scorecard(entries=(entry,)))))
    assert "fragile under the declared input scatter" in read["bearing"]["description"]
