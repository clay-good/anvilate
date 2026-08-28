# Quality-data interchange: verdicts out, calibrated measurements in

**Your CMM software can read Anvilate's verdicts, and a calibration certificate can feed
Anvilate's checks. No translator, no licence fee, and the check that could not run still
says so.**

Anvilate's scorecard is structurally what the metrology world already exchanges: a set of
characteristics, each with a requirement, an evaluated actual, and a status. That is
[QIF](https://qifstandards.org/) — ISO 23952 / ANSI QIF 3.0 — whose schemas are published
free of charge. `export_qif_results` writes the evidence bundle out in it.

```python
from anvilate.export.gate import authorize_export
from anvilate.export.qif import export_qif_results

document = export_qif_results(
    sections,
    part_name="lifting-lug-01",
    spec_digest=spec_digest,
    bom=bom,
    # This card fails, so the export is an explicit override and the header says so.
    authorization=authorize_export(sections.scorecard, override=True),
)
```

The `authorization` is the [export gate](../src/anvilate/export/gate.py): a passing card
authorizes itself, a failing one refuses until the caller overrides, and the header `Scope`
carries the screening notice either way plus an `UNVALIDATED EXPORT` line naming the
blocking checks when it was overridden. This is the one exporter that can see the card it is
exporting — it is in the bundle — so it also refuses an authorization obtained from a
different, passing card.

The worked example is [`examples/lug_scorecard_as_qif.py`](../examples/lug_scorecard_as_qif.py):

```
characteristic    kind         required    actual   status
pin bearing       numeric           2.0       2.7   PASS
net tension       numeric           2.0       1.4   FAIL
weld shear        numeric           2.0       9.1   PASS
plate tear-out    numeric           2.0         —   NOT_ANALYZED
tip deflection    attribute           —      pass   PASS
```

## Four decisions in five rows

**Not-evaluated survives the crossing.** QIF has an enumeration for exactly this state:
`NOT_ANALYZED`. The tear-out check is written as a characteristic that exists, is named,
carries the requirement it *would* have been judged against, and carries no actual. An
exporter that omitted it would produce a file of four characteristics in which every one
had been evaluated — a part whose failure mode nobody looked at, presented as a part fully
examined. (The net-tension FAIL would still be in the file; the *gap* is the harder thing
to notice missing.) No-silent-green is a property of the interchange file too, or it was
never a property at all — and it does not stop being a silent green because it happened
during a format conversion.

**A verdict-only check gets QIF's attribute gauge, not an invented number.** Tip deflection
has no safety factor behind it, so there is no numeric nominal to write. It crosses as a
`UserDefinedAttributeCharacteristicNominal` (with its matching `…Definition`, `…Item`, and
`…Measurement` — QIF names the four aspects separately) carrying declared pass/fail values,
rather than having a threshold made up to fill the slot.

**Over-margin is a pass, and says why.** QIF has no status for a check that passed too
well. The weld-shear check maps to `PASS` — it *is* a pass — with the over-margin finding
stated in the characteristic's `Description`, so the signal crosses even though the
enumeration cannot carry it. Repair hints and fragility warnings ride the same way.

**A numeric check keeps its requirement, and only its requirement.** The required minimum
is written as `MinValue` with `DefinedAsLimit` true, because that is a limit and not a
deviation. A declared upper band is *not* written as a `MaxValue`: in QIF a MaxValue is a
conformance limit and a value past it is nonconforming, while Anvilate's upper band is an
over-engineering flag that never blocks anything. The band is stated in the
characteristic's description instead, where it cannot be mistaken for a tolerance. Safety
factor is dimensionless, so it is declared once as a QIF user-defined unit rather than
borrowed from a linear one.

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

Every verdict in the bundle crosses: the analysis scorecard, the
[typed-callout](typed-callouts.md) layer's own scorecard, and the
[verification plan](verification-planning.md)'s items and unresolved coverage — each tagged
in its description with the layer it came from. Dropping a whole layer of verdicts on the
way out is the same failure as dropping one check, and it is not hypothetical: leaving the
plan out gave a lifter whose proof test cracked it at 108% a characteristic list reading
`PASS`, with the word "cracked" nowhere in the file. The layers that are not
per-characteristic — the reviewer dossier and a design-space sweep — are named in the
header rather than invented as characteristics.

## Determinism

The same evidence exports the same bytes. There are no timestamps, and the document UUID
QIF requires is a digest of the serialized document itself rather than a generated value —
a random one would have destroyed exactly the reproducibility the
[attestation layer](evidence-attestation.md) spends its effort preserving, and a digest of
a few identifying fields would have given two genuinely different documents one identifier.

## The other direction: calibrated measurements in

The chain that ends in a QIF file starts somewhere too, and for a measured value the honest
place to start it is a calibrated instrument. `parse_dcc` reads a Digital Calibration
Certificate (the open PTB schema, DCC v3.3.0 over D-SI v2.2.1) and offers its measured
values to the standard [confirmation flow](requirements-ingestion.md).

```python
from anvilate.dcc import parse_dcc

certificate = parse_dcc(text, document="CAL-2026-04711.dcc.xml")
measured = certificate.labelled("shaft diameter")
draft = DraftSpec(values=(measured.as_extracted("shaft_diameter"),))
```

The worked example is
[`examples/measured_shaft_from_certificate.py`](../examples/measured_shaft_from_certificate.py):
a 25 mm shaft called to ISO 286 h6, measured at 25.0004 mm with an expanded uncertainty of
±0.0012 mm at k = 2. The number fails by 0.4 µm. The certificate's own uncertainty is three
times the overshoot, so the measurement is consistent with an in-tolerance shaft about a
quarter of the time — and Anvilate reports the failure *and* that the measurement does not
settle it.

**A measured value is still a draft.** A calibration certificate is a better source than a
customer's RFQ table; it is not a person deciding that this measurement is the one the
design should use. `release()` refuses until somebody named confirms it, exactly as it does
for an extracted requirement, and the certificate's identity travels with the value through
confirmation — read it off the confirmed `ExtractedValue`, since `release()` hands back a
plain field-to-`Quantity` mapping by design.

**There is no "signature verified".** Verifying an XML digital signature needs the issuer's
certificate and a trust anchor, and a local offline tool has neither. `SignatureStatus` has
two members — `absent` and `present_unverified` — and the value is usable after confirmation
in both cases, with the provenance saying which. The laboratory's own `cryptElectronicSeal`
flag is carried separately as a *claim*: a document asserting that it is sealed is not
evidence that it is.

**A unit outside the table is refused, not guessed at.** D-SI writes units as escape
sequences (`\milli\metre`, `\kilo\gram\metre\tothe{2}\second\tothe{-2}`) over a
vocabulary the published schema leaves as an open string. Every token Anvilate accepts is in
a declared table; anything else is recorded as a value it did not take, naming the token.
Resolving `\bar` to something plausible is how a pressure lands in a check three orders of
magnitude out.

**A stated uncertainty becomes a typed input distribution.** An expanded uncertainty *U* at
coverage factor *k* is a standard uncertainty of *U/k*, which is what
[`Symmetric`](uncertainty-margins.md) means by a half-width at a sigma level, so the
laboratory's number reaches the margin sampler as data rather than as a footnote. The
distribution is always centred on the measured quantity, in that quantity's own unit — ask
for it in the unit your check works in with `distribution_in("mm")`. The sampler sees bare
floats, so the unit has to be settled while the value is still a `Quantity`: the same shaft
stated in micrometres, read raw, is sampled a thousandfold off against a millimetre limit
with nothing in the numbers to show it.

| The certificate states | Anvilate hands over |
| --- | --- |
| expanded uncertainty *U* at *k* | `Symmetric(nominal=…, half_width=U, distribution="normal", sigma_level=k)` |
| standard uncertainty *u* | `Normal(mean=…, std=u)` |
| a coverage interval | `Normal(std=…)` from its stated standard uncertainty |
| an expanded *U* with no usable *k* | nothing, and says why — k = 2 is a convention, not this certificate's statement |
| a non-Gaussian distribution | nothing, and names it — a rectangular uncertainty and a normal one of the same width are different statements |

## Drawing callouts cross too: GD&T as characteristic definitions

A feature control frame and a QIF characteristic definition describe the same thing, so
`qif_characteristic_mapping(frame)` puts one in the other's vocabulary.

```python
from anvilate.export.qif import qif_characteristic_mapping
```

```text
⌖ | Ø0.2 mm Ⓜ | A | B Ⓜ | C

definition_type   PositionCharacteristicDefinitionType
tolerance_mm      0.2
material_modifier MAXIMUM
zone_shape        DiametricalZone
datums            A REGARDLESS | B MAXIMUM | C REGARDLESS
```

**Every name there was read out of the published schema, and three of them would have been
guessed wrong.** QIF spells profile-of-a-line `LineProfile`. Its material-modifier
enumeration is `REGARDLESS` / `MAXIMUM` / `LEAST`, not the drawing abbreviations — a
document emitting `MMC` does not validate. And the non-diametral zone element is
`NonDiametricalZone` for position but `PlanarZone` for the orientation characteristics, so
one name reused for both is a document that fails on the second callout. All of it is held
against the XSD by a test that CI runs against the real download.

**A modifier the target type cannot hold is refused, not dropped.** Six of the fourteen
definition types carry a `MaterialCondition` element; the rest have nowhere to put one. A Ⓜ
that vanishes on the way out crosses as a *tighter* requirement than the drawing granted,
and the receiving inspection program has no way to know a modifier was ever there — the
same silent-green shape the tri-state rule above exists to prevent, in the other direction.

**This is the definition mapping, not a document writer.** QIF's `DatumType` requires a
`DatumDefinitionId` pointing at a datum definition anchored to a feature, and a feature
control frame knows only the letter. What a caller still owes comes back in `unresolved`,
named one item at a time, rather than defaulted: a datum reference frame invented by the
exporter is an inspection instruction nobody authored. A frame that needs nothing more —
flatness on a surface, no datums, no modifiers — returns an empty tuple.

## Checking a document

`qif_schema_issues(document)` does the structural checks that need nothing but the file:
root element and namespace, the `idMax` claim against the ids actually present, id
uniqueness, every `n` count against what it counts, and every internal reference resolving.
An empty list means the document is self-consistent — not that it is schema-valid.

Schema validation is the real conformance check and it is opt-in on both sides, because the
schemas are separate (free) downloads and the parser is not a runtime dependency:

```bash
ANVILATE_QIF_XSD=/path/to/QIF3.0/xsd pytest tests/test_qif.py -k schemas
```

```bash
ANVILATE_DCC_XSD=/path/to/dcc pytest tests/test_dcc.py -k schema
```

Without the schemas and `lxml`, those tests skip rather than passing — an unrunnable check is
reported as not run, which is the same rule the scorecard follows.

CI runs them for real. The `interchange-schemas` job fetches both schema packages, points
their imports at the local copies, and runs the two validations by name — then **fails if
either skipped**, because a job that goes green on a check that never ran is the same silent
pass in a different costume. It runs weekly and on demand rather than on every push: it
depends on two external hosts, and a flaky download should not block a pull request that has
nothing to do with either format. A schema republished upstream shows up there as a failure
rather than as a surprise in somebody's quality software.
