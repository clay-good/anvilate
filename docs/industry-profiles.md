# Industry profiles

**Declare once how your industry or company screens, and every rule it adds is on the
card with its source.** A spacecraft engineer, an automotive engineer and a machine
builder screen the same bracket under different rules: which factors apply, which checks
are mandatory for a class of item, which records must come out. A profile is those rules
as data.

A profile is a screening configuration. It is never a certification or a regulatory
determination, and every card and listing made under one says so.

## What a profile holds

| Rule | Example | Effect |
| --- | --- | --- |
| `factors` | `ultimate = 1.5` | named factors; a layered override that lowers one is reported as a relaxation |
| `factor_set` | NASA-STD-5001B | the factor set the margin table is computed under |
| `required_checks` | random vibration for every `avionics box` | the check appears on the card even when nothing triggered it |
| `required_artifacts` | `margin_table`, `dfmea`, `risk_file` | the records the program expects |
| `drawing_standard` | ASME Y14.5-2018 | the tolerancing standard |

Every rule has an `id` and either a `source` (document and clause) or
`practice_default: true`. A rule with neither is refused, naming it. A profile is
identified by a URN and a version, declares its own `item_classes`, and is validated
against [its published schema](api/schemas/industry-profile.schema.json):

```yaml
urn: urn:acme:profile:transport-aircraft
name: Transport aircraft
version: 0.1.0
item_classes: [avionics box, primary structure]
factors:
  - {id: TA-F-1, name: ultimate, value: 1.5, source: "14 CFR 25.303 factor of safety"}
required_checks:
  - id: TA-VIB-1
    source: "RTCA DO-160G §8 vibration"
    item_class: avionics box
    check: random vibration
    satisfied_by: [random vibration]
    needs: [input PSD (g²/Hz against Hz), duration]
    analysis: anvilate.analysis.random_vibration.miles_response_grms
```

## Applying one

```python
from anvilate.industry import apply_profile, load_profile, resolve

profile = resolve(load_profile(text))
profiled = apply_profile(card, profile, item_class="avionics box")
profiled.card            # the card, with each required check on it
profiled.added           # ('random vibration',) when nothing on the card ran it
print(profile)           # the header, then everything the profile changed, rule by rule
```

From the shell, `--profile` takes a shipped name or a profile file (layered on the shipped
profile it `extends`), and the card opens with the profile's header and every rule it
changed; `--format json` carries the same under `profile`:

```text
anvilate check bracket.yaml --profile spaceflight --item-class "flight box"
anvilate check bracket.yaml --profile acme-aero.yaml
```

Over MCP, `run_validation` takes `profile` (a shipped profile's name) and screens under it
for the spec's own `item_class`; its result carries `profile`, the same header and changes
with the checks the profile added
([profile-listing 1.0.0](api/schemas/profile-listing.schema.json)).

A part can declare its class in its own Design Spec, `item_class: flight box`, and
`--item-class` is then needed only to override it; a class the profile does not declare is
refused, naming the file. Without a profile the field is inert. A required check that has
not run leaves the card not evaluated, so the exit code is 2 until it does.

| A required check | Shows as |
| --- | --- |
| already on the card (its `check_id` or name matches `satisfied_by`) | itself, unchanged |
| not on the card | **not evaluated**, naming the inputs in `needs` |
| its `pack` or `analysis` missing from this installation, or `implemented: false` | **not available**, naming what is missing and the `install` command |

A required check is never dropped. Each entry a profile adds carries a reference naming
the profile, its version, the rule's id and its source. A calculation report built with
`CalculationReport(..., profile=resolved.profile.label)` names the profile in its header,
in text, HTML and PDF, beside the statement that it is not a certification.

## Layering a company profile

A company profile names the profile it `extends` and adds rules or overrides factors, each
with its own source. `layer(parent, child)` resolves the pair: the child's factors replace
the parent's by name, its required checks and artifacts are added, and a required check is
never removed.

An override that **lowers** a factor is a relaxation. It is reported with both values and
both sources, and listed among the profile's changes:

```text
RELAXED ultimate: 1.4 (ACME ES-12 §4, test-verified) below 1.5 (14 CFR 25.303 factor of safety)
```

## Shipped profiles

`bundled_profiles()` returns them; `industry_profile("spaceflight")` picks one by name.
Each is a starting point read from public documents, edition by edition, to layer your
program's or company's profile on. What it could not fill from a public document is listed
under `awaiting`, naming where your licensed copy gives the value.

| Profile | Factors | Required for | Awaiting your value |
| --- | --- | --- | --- |
| `general` | none | nothing | nothing |
| `spaceflight` | ultimate 1.4, yield 1.25 (GSFC-STD-7000B Table 2.2-3, static and sine) | flight box: random vibration (GEVS §2.4.2.5, at least the Table 2.4-4 workmanship levels) and outgassing (NASA-STD-6016C §4.2.3.6, ASTM E595: CVCM ≤0.1%, TML ≤1.0%); primary structure: outgassing | nothing |
| `medical-device` | none | records: risk file, DVP&R and trace (21 CFR 820.10(a) and (c), QMSR in force from 2026-02-02, through ISO 13485) | your risk-management plan's categories (ISO 14971); biological evaluation endpoints (ISO 10993-1) |
| `industrial-machinery` | none | machine part: strength in use (Regulation (EU) 2023/1230 Annex III 1.3.2); guard: strength (1.4.1, 1.4.2); records: risk file (Annex III Part B point 1), design calculations (Annex IV Part A (g)) | safety distances and guard load cases from the harmonised standards |
| `automotive` | none | chassis part: fatigue; records: DFMEA, DVP&R, control-plan seed, characteristic table, all practice defaults: no public document governs them | your customer's FMEA tables and matrix; their special-characteristic symbols |
| `consumer-product` | none | children's article: sharp edge and sharp point (16 CFR 1500.49, 1500.48), shown **not available**: no screen here computes them yet | nothing |
| `transport-aircraft` | ultimate 1.5 (14 CFR 25.303), fitting 1.15 (25.625) | primary structure and fittings: fatigue and damage tolerance (25.571) | material design values at the 25.613 probabilities; a bearing factor, for which 25.623 sets no number |

`general` adds nothing: no factors, no required checks, no artifacts. Applying it leaves
every shipped example's card unchanged, which a test holds over all of them, and its list
of changes is empty.

## Not yet

- Relaxations carried onto the rows of a margin table.
