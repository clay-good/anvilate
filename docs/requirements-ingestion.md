# Requirements ingestion

**An extracted value is a draft, and a draft is not an input.** `DraftSpec.release()`
refuses while any load-bearing value is unconfirmed, and it names them. That refusal is
the feature; everything else here exists to make it answerable.

Engineers start from a requirement sheet, not a chat box — an RFQ table, a customer
requirement sheet, an internal design brief — and the values in it are the loads,
environments, and acceptance criteria the whole screening rests on.

```python
from anvilate.ingest import extract_requirements

sheet = Path("rfq-2026-114.txt").read_text()
draft = extract_requirements(sheet, document="rfq-2026-114.txt")
draft.release()
# ValueError: 4 load-bearing value(s) are still drafts and nobody has confirmed them:
#   ['bore_diameter', 'design_load', 'rated_capacity', 'service_temperature'].
#   An extracted value is a draft, and a draft is not an input
```

(The count is *values* and the list is *distinct fields*, so a sheet stating one field
twice reports more values than names. That is deliberate: the count is how much is
outstanding and the list is what to go and look at.)

## Five positions

**No confidence scores.** A number between 0 and 1 on an extraction invites somebody to
set a threshold and stop reading, and it is not a measurement of anything — it is the
extractor grading its own homework. Every `ExtractedValue` instead carries the exact line
it came from and where that line was, so "is this right?" is answered by looking.

**A bare number is not a quantity.** A sheet says `design load: 50 kN` and it also says
`quantity: 4`. No amount of context turns an unlabelled 4 into a physical value. A line
whose value has no unit becomes an `UnparsedLine` with the reason, so the pass is auditable
by *subtraction* — a reader can see what it did not take instead of assuming it took
everything.

**A conflict is surfaced, never resolved.** The table says 50 kN and the note says 45 kN.
Both are kept, both are reported, and the release stays blocked **even if both sides are
confirmed** — two values for one field is not a field. Picking the first, the last, or the
larger is a silent decision about the design.

**A limit keeps the direction it was written with.** `Maximum operating pressure: 5 bar`
and `minimum yield: 250 MPa` are not the same kind of statement, and a number that has lost
which end of a range it is reads as a design value when it is a ceiling. Every
`ExtractedValue` carries a `Bound` — `maximum`, `minimum`, or `unstated` — taken from the
label or from the trailing qualifier. `unstated` is the honest default and does not mean
"nominal": it means nobody said.

**Confirmation is per value and names a person.** Not per document, not per session. A
`CONFIRMED` or `REJECTED` state with nobody named is refused at construction, because "the
values were reviewed" is not a claim anybody can act on.

## The checklist is what you actually work from

`draft.checklist()` lists every value with the line it came from, because confirming an
extracted number means opening the sheet and reading that line:

```text
5 values from 1 document(s), 1 confirmed, 1 lines not extracted — blocked: 3 unconfirmed, 1 conflicting, 0 split across two bounds

TO CONFIRM — load-bearing, blocking release
  [ ] design_load = 50.0 kN    rfq.pdf:14 (p. 2) — 'Design load: 50 kN'
  [ ] plate_thickness = 12.00 mm    rfq.pdf:7 (p. 3) — 'Plate 12 mm'
  [ ] design_load = 60.0 kN    rfq.pdf:3 (p. 5) — 'Load shall be 60 kN'

TO CONFIRM — not load-bearing
  [ ] finish_area = 0.500 m ** 2    rfq.pdf:2 (p. 4) — 'Painted area 0.5 m2'

CONFIRMED
  [x] material_yield = 250.0 MPa    rfq.pdf:9 (p. 1) — 'A36' — confirmed by A. Engineer

CONFLICTS
  !   design_load disagrees:
        design_load = 50.0 kN    rfq.pdf:14 (p. 2) — 'Design load: 50 kN'
        design_load = 60.0 kN    rfq.pdf:3 (p. 5) — 'Load shall be 60 kN'

NOT EXTRACTED
  ?   rfq.pdf:22 (p. 6) — 'approx 3/8 in stock' — no parseable quantity
```

`summary()` gave the counts — "3 unconfirmed" — which is the one thing the confirmer
already knows. Every value carried its `SourceLocation` from the first release and nothing
rendered it.

Three things about the shape:

- **The excerpt is part of the reference, not an extra.** A reader holding the sheet open
  matches on the text faster than on a line number, and a line number alone is wrong the
  moment the document is re-exported.
- **A conflict shows both readings.** Naming the field tells you there is a problem and
  nothing about it; the two excerpts side by side are what decide which line is right.
- **Every heading appears even when its section is empty**, for the same reason the
  [calculation report](calculation-reports.md)'s do: a draft with no conflicts and one whose
  conflicts nobody looked for must not render the same document.

## Three states, not a boolean

| State | Means |
| --- | --- |
| `DRAFT` | nobody has looked at it; blocks the release if load-bearing |
| `CONFIRMED` | a named person accepted it; the only state a check may consume |
| `REJECTED` | a named person looked at it and refused it — a decision, kept in the record |

`REJECTED` earns its place: "somebody refused this" is different information from "nobody
has looked at this yet", and collapsing them loses the audit trail on exactly the values
somebody argued about.

## What it declines, and why declining is the point

A value the pass declines costs somebody a minute. A value it gets **wrong** is a load. So
where a line could plausibly be read two ways, it is declined and recorded:

| Line | Would have been | Now |
| --- | --- | --- |
| `Design load: 45–50 kN` | **2250 kN** — pint multiplied the range out | declined as a range |
| `Bore: 25 ±0.1 mm` | **2.5 mm** | declined as a tolerance |
| `Span: 1,5 m` | **15 m** — a tenfold error on a European sheet | declined as an ambiguous comma |
| `Temp: 20 C` | 20 **coulomb** | declined; write `degC` |
| `Temp: 20 c` | 20 × **the speed of light** | declined; write `degC` |
| `Grade: 8.8 min` | 8.8 **minutes** | declined; write `minute` if you mean time |
| `Minimum bore: 30 mm max` | 30 mm, one end silently chosen | declined; the line states both ends |
| `Pressure: 5 bar g` | bar·**gram** | declined; a gauge marker is not a unit |

The en dash matters more than it looks: it is what a word processor autocorrects `45-50`
into, and the hyphen spelling was already being declined — so the defence was
spelling-luck rather than a rule. The rule underneath all of these is one line: **if the
parsed magnitude is not the magnitude the document stated, the unit half carried a number
of its own**, whatever the punctuation was.

## Which end of the range it is

A requirement sheet states ceilings and floors, not design values, and the direction is
carried on the value rather than left in the field name:

| Line | Field | Bound |
| --- | --- | --- |
| `Design load: 50 kN max` | `design_load` | `maximum` |
| `Maximum operating pressure: 5 bar` | `maximum_operating_pressure` | `maximum` |
| `Bore: 25 mm` | `bore` | `unstated` |

`Design load: 50 kN max` used to be declined whole — `max` is a qualifier, and refusing the
qualifier refused the quantity with it. It is now the most common line the pass takes.

The label phrases are matched as whole words (`maximum`, `max`, `not to exceed`, `no more
than`, `at most`, `up to`, and their minimum counterparts), never as substrings: `min` is a
substring of `nominal`, and a nominal dimension read as a floor is exactly the confident
wrong answer everything else here refuses. A line whose label and value state *opposite*
ends (`Minimum bore: 30 mm max`) is declined rather than resolved.

**The field name is not rewritten.** `maximum_operating_pressure` stays that, rather than
becoming `operating_pressure` with a bound beside it. Renaming would merge two fields on
the extractor's own authority, and merging is the decision this module hands to a person.

Two bounds on one field are **not a conflict** — `design load: 50 kN max` and `design load:
20 kN min` are the two ends of one range, and reporting them as disagreeing sends somebody
to reject a requirement the sheet meant. They still cannot both be released: the released
mapping has one slot per field, so `release()` refuses and names the field, and
`summary()` counts it rather than printing `releasable` over a draft the gate will refuse.
Resolve it the way this module resolves everything — reject the end the check does not
consume, which leaves a record that somebody chose.

## What the pass reads

A line is `label<separator>value`, where the separator is a colon, an equals sign, or a
column gap of two or more spaces (a flattened fixed-width table). A single space is
deliberately not a separator — `design load 50 kN` would split at the first space and
label the field `design`.

Labels normalize to stable field names (`Design Load (max):` → `design_load_max`). The
magnitude tolerates thousands separators. Offset temperature units work: pint will not
*parse* `-20 degC` from text, only construct it, and every real requirement sheet has a
service temperature on it. That is handled at the front door now — `Quantity.parse`
takes `-20 degC` and `400 °C` — rather than by this pass alone, because a unit the
library renders and cannot re-read is one a *spec* cannot state either.

`load_bearing` defaults to True, and that default is the safe direction — a value nobody
classified blocks the release until somebody looks at it, rather than slipping through as
decoration. Name the exceptions with `informational_fields`.

## Scope

The pass is label-driven, over plain text, and knows nothing about engineering vocabulary.
That is deliberate: a pass that guessed which line was "really" the design load would be
making the decision this module exists to hand to a person.

PDF and table extraction belong with the document stack and land with it. The state
machine does not change when they do — a `SourceLocation` already carries a page number.

## Worked example

`examples/rfq_sheet_to_confirmed_inputs.py` — eight labelled lines, five taken and three
recorded as unparsed, a sheet that contradicts itself, a release that stays blocked
through confirmation, and a rejection that resolves it and stays in the record.
