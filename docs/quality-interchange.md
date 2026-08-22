# Quality-data interchange: the scorecard as QIF Results

**Your CMM software can read Anvilate's verdicts. No translator, no licence fee, and the
check that could not run still says so.**

Anvilate's scorecard is structurally what the metrology world already exchanges: a set of
characteristics, each with a requirement, an evaluated actual, and a status. That is
[QIF](https://qifstandards.org/) — ISO 23952 / ANSI QIF 3.0 — whose schemas are published
free of charge. `export_qif_results` writes the evidence bundle out in it.

```python
from anvilate.export.qif import export_qif_results

document = export_qif_results(
    sections, part_name="lifting-lug-01", spec_digest=spec_digest, bom=bom
)
```

The worked example is [`examples/lug_scorecard_as_qif.py`](../examples/lug_scorecard_as_qif.py):

```
characteristic    kind         required    actual   status
pin bearing       numeric           2.0       2.7   PASS
net tension       numeric           2.0       1.4   FAIL
weld shear        numeric           2.0       9.1   PASS
plate tear-out    numeric           2.0         —   NOT_ANALYZED
tip deflection    attribute           —      pass   PASS
```

## The four rows are four decisions

**Not-evaluated survives the crossing.** QIF has an enumeration for exactly this state:
`NOT_ANALYZED`. The tear-out check is written as a characteristic that exists, is named,
carries the requirement it *would* have been judged against, and carries no actual. An
exporter that omitted it would produce a file in which four of four characteristics pass.
No-silent-green is a property of the interchange file too, or it was never a property at
all — and it does not stop being a silent green because it happened during a format
conversion.

**A verdict-only check gets QIF's attribute gauge, not an invented number.** Tip deflection
has no safety factor behind it, so there is no numeric nominal to write. It crosses as a
`UserDefinedAttributeCharacteristic` with declared pass/fail values, rather than having a
threshold made up to fill the slot.

**Over-margin is a pass, and says why.** QIF has no status for a check that passed too
well. The weld-shear check maps to `PASS` — it *is* a pass — with the over-margin finding
stated in the characteristic's `Description`, so the signal crosses even though the
enumeration cannot carry it. Repair hints and fragility warnings ride the same way.

**A numeric check keeps its band.** The required minimum is written as `MinValue`, a
declared upper band as `MaxValue`, with `DefinedAsLimit` true because those are limits, not
deviations. Safety factor is dimensionless, so it is declared once as a QIF user-defined
unit rather than borrowed from a linear one.

| Anvilate | QIF characteristic status | Document `InspectionStatus` |
| --- | --- | --- |
| `PASS` | `PASS` | `PASS` |
| `OVER_MARGIN` | `PASS` (finding in the description) | `PASS` |
| `FAIL` | `FAIL` | `FAIL` |
| `NOT_EVALUATED` | `NOT_ANALYZED` | `NOT_CALCULATED` |

The two enumerations spell the last row differently. They are separate lists in the schema,
and mapping one from the other by string emits a document that does not validate.

## What travels with the verdicts

The spec digest and the bundle's own roll-up go in the document header. Every citation the
evidence collected becomes a `Standard` in `StandardsDefinitions`. Every BOM component
becomes a `Software` entry — so the file records which Anvilate, against which versioned
databases, screened which spec revision. The header's `Scope` line states plainly that
these are T1 screening results and not a certified analysis or a physical inspection.

Every check in the bundle crosses, including the [typed-callout](typed-callouts.md) layer's
own scorecard, each tagged in its description with the layer it came from. Dropping a whole
layer of verdicts on the way out is the same failure as dropping one check.

## Determinism

The same evidence exports the same bytes. There are no timestamps, and the document UUID
QIF requires is derived from the content rather than generated — a random one would have
destroyed exactly the reproducibility the [attestation layer](evidence-attestation.md)
spends its effort preserving.

## Checking a document

`qif_schema_issues(document)` does the structural checks that need nothing but the file:
root element and namespace, the `idMax` claim against the ids actually present, id
uniqueness, every `n` count against what it counts, and every internal reference resolving.
An empty list means the document is self-consistent — not that it is schema-valid.

Schema validation is the real conformance check and it is opt-in, because the schemas are a
separate (free) download and the parser is not a runtime dependency:

```bash
ANVILATE_QIF_XSD=/path/to/QIF3.0/xsd pytest tests/test_qif.py -k schemas
```

Without both, that test skips rather than passing — an unrunnable check is reported as not
run, which is the same rule the scorecard follows.
