"""Worked example: the scorecard handed to quality software, without a translator.

A lifting lug screens to four checks — one comfortable pass, one failure, one that ran so
far past its target band it is over-engineered, and one that could not run at all because
the tear-out path was never dimensioned. That last one is the interesting one.

Exported as QIF Results (ISO 23952), a CMM package or a quality system reads all four as
*characteristics*: each with the requirement it was judged against, the actual that was
computed, and a status. The point of the crossing is what happens to the fourth:

* the failing check crosses as ``FAIL`` with its actual and its repair direction,
* the over-margin check crosses as ``PASS``, because QIF has no "passed too well", with
  the finding stated in the characteristic's description rather than dropped,
* and the check that could not run crosses as ``NOT_ANALYZED`` — present, named, carrying
  the requirement it *would* have been judged against and no actual at all.

An exporter that quietly omitted the fourth would produce a file of four characteristics
in which every one had been evaluated — a part whose failure mode nobody looked at,
presented as a part fully examined. The document would still carry the net-tension FAIL;
what it would lose is the *gap*, which is the harder thing to notice missing. That is the
silent green this library exists to refuse, and it does not stop being one because it
happened during a format conversion.

The verdict-only check is the second decision worth seeing: "tip deflection" has no safety
factor, so there is no numeric nominal to write. It crosses as a QIF *attribute*
characteristic — pass/fail values, no invented number — rather than having a threshold
made up to fill the slot.

Run it directly (``python examples/lug_scorecard_as_qif.py``);
:func:`lug_as_qif` is exercised in the test suite.
"""

from __future__ import annotations

from xml.etree import ElementTree as ET

from anvilate.attestation import Component, ComponentKind, EnvironmentBOM
from anvilate.bundle import BundleSections
from anvilate.evidence import SourceRecord
from anvilate.export.qif import QIF_NAMESPACE, export_qif_results
from anvilate.scorecard import CheckStatus, Direction, RepairHint, Scorecard, ScorecardEntry

SPEC_DIGEST = "sha256:2f1a9c4d6b8e0a3c5d7f9b1e3a5c7d9f0b2e4a6c8d0f2b4e6a8c0d2f4b6e8a0c"

LUG = Scorecard(
    entries=(
        ScorecardEntry.from_safety_factor("pin bearing", computed=2.7, required=2.0),
        ScorecardEntry.from_safety_factor(
            "net tension",
            computed=1.4,
            required=2.0,
            repair_hint=RepairHint.directional("plate_thickness", direction=Direction.INCREASE),
        ),
        # Passing, and passing so hard it is worth saying: a 4.0 target band, a 9.1 actual.
        ScorecardEntry.from_safety_factor("weld shear", computed=9.1, required=2.0, upper=4.0),
        # The tear-out path was never dimensioned, so the check could not run.
        ScorecardEntry.from_safety_factor("plate tear-out", computed=None, required=2.0),
        # A serviceability check with a verdict and no safety factor behind it.
        ScorecardEntry(
            name="tip deflection",
            status=CheckStatus.PASS,
            detail="span/360 met",
            reference="AISC 360-22 L3",
        ),
    )
)

BOM = EnvironmentBOM(
    application=Component(name="anvilate", version="0.0.1", kind=ComponentKind.APPLICATION),
    components=(
        Component(name="pint", version="0.24"),
        Component(name="anvilate_materials", version="2026.03", kind=ComponentKind.DATA),
    ),
)

SECTIONS = BundleSections(
    scorecard=LUG,
    citations=(
        SourceRecord(
            ref="A36",
            kind="material",
            name="ASTM A36",
            sources=("ASTM A36 specified minimum (specification minimum)",),
        ),
    ),
)


def lug_as_qif() -> str:
    """The lug's evidence as a QIF Results document."""
    return export_qif_results(
        SECTIONS, part_name="lifting-lug-01", spec_digest=SPEC_DIGEST, bom=BOM
    )


def read_back(document: str) -> list[dict[str, str | None]]:
    """Read the document the way a quality package would: items, nominals, measurements.

    Nothing here knows what the exporter intended — it walks QIF's own structure, which is
    the only thing a third-party reader has.
    """
    ns = {"q": QIF_NAMESPACE}
    root = ET.fromstring(document)
    nominals = {
        n.get("id"): n for n in root.findall("./q:Characteristics/q:CharacteristicNominals/*", ns)
    }
    items = {}
    for item in root.findall("./q:Characteristics/q:CharacteristicItems/*", ns):
        nominal = nominals[item.findtext("q:CharacteristicNominalId", namespaces=ns)]
        items[item.get("id")] = {
            "name": item.findtext("q:Name", namespaces=ns),
            "required": nominal.findtext("q:MinValue", namespaces=ns),
            "kind": "attribute" if "Attribute" in nominal.tag else "numeric",
        }

    read: list[dict[str, str | None]] = []
    for measurement in root.findall(
        "./q:Results/q:MeasurementResultsSet/q:MeasurementResults"
        "/q:MeasuredCharacteristics/q:CharacteristicMeasurements/*",
        ns,
    ):
        record = dict(items[measurement.findtext("q:CharacteristicItemId", namespaces=ns)])
        record["status"] = measurement.findtext(
            "q:Status/q:CharacteristicStatusEnum", namespaces=ns
        )
        record["actual"] = measurement.findtext("q:Value", namespaces=ns)
        read.append(record)
    return read


def main() -> None:
    document = lug_as_qif()
    print(
        f"QIF Results document: {len(document)} bytes, {len(read_back(document))} characteristics"
    )
    print()
    print(f"{'characteristic':<18}{'kind':<11}{'required':>10}{'actual':>10}   status")
    for record in read_back(document):
        required = record["required"] or "—"
        actual = record["actual"] or "—"
        print(
            f"{record['name']:<18}{record['kind']:<11}{required:>10}{actual:>10}   "
            f"{record['status']}"
        )
    print()
    records = read_back(document)
    evaluated = sum(1 for record in records if record["status"] != "NOT_ANALYZED")
    print("The tear-out row is the one that matters: a reader enumerating this file sees a")
    print("characteristic that was NOT_ANALYZED, with the requirement it would have been")
    print(f"judged against and no actual. {evaluated} of {len(records)} characteristics were")
    print(f"evaluated; omitting it would have made that {evaluated} of {evaluated} — a part")
    print("whose failure mode nobody looked at, reported as one fully examined.")
    print()
    print("Deterministic:", lug_as_qif() == document)


if __name__ == "__main__":
    main()
