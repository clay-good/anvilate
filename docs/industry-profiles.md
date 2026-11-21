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

| A required check | Shows as |
| --- | --- |
| already on the card (its `check_id` or name matches `satisfied_by`) | itself, unchanged |
| not on the card | **not evaluated**, naming the inputs in `needs` |
| its `pack` or `analysis` missing from this installation | **not available**, naming what is missing and the `install` command |

A required check is never dropped. Each entry a profile adds carries a reference naming
the profile, its version, the rule's id and its source.

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

## The general profile

`GENERAL` adds nothing: no factors, no required checks, no artifacts. Applying it leaves
every card unchanged, and its list of changes is empty.

## Not yet

- Item classes declared on the Design Spec itself; today the class is passed to
  `apply_profile`.
- Shipped profiles for spaceflight, transport aircraft, automotive, medical devices,
  industrial machinery and consumer products, read from public documents.
- Relaxations carried onto the rows of a margin table, and the profile header in reports
  and over the MCP tools and the CLI.
