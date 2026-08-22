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

## Four positions

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

**Confirmation is per value and names a person.** Not per document, not per session. A
`CONFIRMED` or `REJECTED` state with nobody named is refused at construction, because "the
values were reviewed" is not a claim anybody can act on.

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
| `Grade: 8.8 min` | 8.8 **minutes** | declined; write `minute` if you mean time |
| `Pressure: 5 bar g` | bar·**gram** | declined; a gauge marker is not a unit |

The en dash matters more than it looks: it is what a word processor autocorrects `45-50`
into, and the hyphen spelling was already being declined — so the defence was
spelling-luck rather than a rule. The rule underneath all of these is one line: **if the
parsed magnitude is not the magnitude the document stated, the unit half carried a number
of its own**, whatever the punctuation was.

## What the pass reads

A line is `label<separator>value`, where the separator is a colon, an equals sign, or a
column gap of two or more spaces (a flattened fixed-width table). A single space is
deliberately not a separator — `design load 50 kN` would split at the first space and
label the field `design`.

Labels normalize to stable field names (`Design Load (max):` → `design_load_max`). The
magnitude tolerates thousands separators. Offset temperature units work: pint will not
*parse* `-20 degC` from text, only construct it, and every real requirement sheet has a
service temperature on it.

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
