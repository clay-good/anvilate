---
name: anvilate
description: Screen a mechanical or structural part against cited engineering checks with Anvilate, and report the result the way an engineer would. Use when asked to size, check, or validate a part, joint, member, or vessel, or to interpret an Anvilate scorecard.
version: 0.0.1
tool-surface: the anvilate Python API. Every symbol named below is resolved against the live importable surface in CI, so a renamed function fails the build rather than shipping as advice.
license: MIT
---

# Anvilate

Anvilate turns a described part into a **scorecard**: one typed result per check, each
citing the clause it came from. It is a T1 analytical screening library — closed-form,
unit-checked, and fast — and it is not a certified analysis.

This file is documentation. It grants nothing. Every rule below is enforced by the
library whether or not you loaded this, and the same calls produce the same results
either way.

## The four things agents get wrong

1. Recalling a standard dimension instead of retrieving it.
2. Reporting success without reading the scorecard.
3. Reading "not evaluated" as a pass.
4. Presenting a screening result as a certified analysis, which it is not.

Each has a section below, and each section's claim is carried by a worked example that
runs in CI.

## 1. Retrieve, do not recall

<!-- doctrine: retrieval-not-recall -->

Standard dimensions live in the bundled databases with their citations attached. Look
them up. A remembered width-across-flats is a number with no provenance, and Anvilate's
whole product is provenance.

```python
from anvilate.standards import default_hex_bolt_table

bolts = default_hex_bolt_table()
bolt = bolts.get("ISO4014-M12")
print(bolt.width_across_flats.quantity)
print(bolt.citations()["width_across_flats"].source)
```

```text
18 mm
ISO 4014 / ISO 4017 hexagon-head bolt and screw head dimensions
```

An unknown designation is refused with the near misses named, rather than resolved to
something plausible:

```python
from anvilate.standards import default_hex_bolt_table
from anvilate.standards.hexbolts import UnknownHexBoltError

try:
    default_hex_bolt_table().get("M12")
except UnknownHexBoltError as exc:
    print("refused:", exc)
```

```text
refused: "no record for hex bolt 'M12'"
```

Do not paper over that refusal by supplying the number yourself. Ask which record is
meant, or say the database does not carry it.

## 2. Read the scorecard before you report

<!-- doctrine: read-the-scorecard -->

Every check returns a `ScorecardEntry` with a tri-state status. Roll them into a
`Scorecard` and report `status`, not your impression of how the calculation went.

```python
from anvilate.analysis import bolt_shear_stress, strength_scorecard
from anvilate.scorecard import Scorecard, ScorecardEntry
from anvilate.units import Quantity

shear = bolt_shear_stress(force=Quantity.parse("8 kN"), diameter=Quantity.parse("8 mm"))
bolt = strength_scorecard(
    "bolt shear", stress=shear, allowable=Quantity.parse("380 MPa"), required=1.5
)
tearout = ScorecardEntry.from_safety_factor("plate tear-out", computed=None, required=2.0)
card = Scorecard(entries=(bolt, tearout))

governing = card.governing()
print(card.status.value, "|", "None" if governing is None else governing.name)
print(bolt.detail)
```

```text
not_evaluated | plate tear-out
safety factor 2.39 vs required minimum 1.50
```

`card.governing()` names the check to quote, and its ordering is **blocking status first,
then highest utilization**: a failing check outranks one that could not run, which outranks
every passing check however close to its limit. So the tear-out check governs here at a
utilization of `None`, ahead of a bolt at 63% — pointing you at the thing that blocks rather
than at the tightest number.

It returns `None` when nothing blocks and no check carries a safety factor, which every
deflection-only card looks like. Write `card.governing()` into a variable and check it;
`card.governing().name` raises `AttributeError` on exactly those cards.

## 3. "Not evaluated" is not a pass

<!-- doctrine: not-evaluated-is-not-a-pass -->

A check that could not run reports `NOT_EVALUATED`. It is not a pass, and it does not
become one by going unmentioned. A scorecard containing one is never `passed`.

```python
from anvilate.scorecard import CheckStatus, Scorecard, ScorecardEntry

gap = ScorecardEntry.from_safety_factor("plate tear-out", computed=None, required=2.0)
good = ScorecardEntry.from_safety_factor("pin bearing", computed=2.7, required=2.0)
card = Scorecard(entries=(good, gap))

assert gap.status is CheckStatus.NOT_EVALUATED
assert gap.passed is False
assert card.status is CheckStatus.NOT_EVALUATED
assert card.passed is False
print(card.status.value, "|", len(card.not_evaluated()), "not evaluated")
```

```text
not_evaluated | 1 not evaluated
```

When you report, name the unevaluated checks and say what is missing. "Two of three
checks pass" is a true sentence that reads as a passing part; do not write it.

## 4. Repair with the inverse first

<!-- doctrine: inverse-first-repair -->

A failing check carries a `repair_hint` naming the parameter and the direction. Where a
design inverse exists, it solves for the value that lands exactly at the required margin
— one call instead of a search. Reach for the inverse before you start guessing sizes.

```python
from anvilate.analysis.fastener import bolt_diameter_for_shear, bolt_shear_stress
from anvilate.units import Quantity

load = Quantity.parse("8 kN")
allowable = Quantity.parse("380 MPa")
needed = bolt_diameter_for_shear(
    shear_load=load, allowable_shear=allowable, required_safety_factor=2.0
)
achieved = (
    allowable.to("MPa").magnitude
    / bolt_shear_stress(force=load, diameter=needed).to("MPa").magnitude
)
print(f"{needed.to('mm').magnitude:.3f} mm gives SF {achieved:.3f}")
```

```text
7.322 mm gives SF 2.000
```

The inverse lands *exactly* at the required margin, never above it. Rounding up to a
stock size is a decision for the engineer, and it is one you should state rather than
make silently.

## 5. Confirm inputs; a draft is not an input

<!-- doctrine: confirm-before-use -->

Values read out of a requirements document or a calibration certificate arrive as
drafts. `release()` refuses while any load-bearing value is unconfirmed, and it names
them. Do not work around that by reading the drafts directly.

```python
from anvilate.ingest import extract_requirements

draft = extract_requirements("design load: 50 kN\nbore diameter: 25 mm", document="rfq.txt")
try:
    draft.release()
except ValueError as exc:
    print("blocked:", str(exc).split(".")[0])
released = (
    draft.with_confirmation("design_load", by="R. Engineer")
    .with_confirmation("bore_diameter", by="R. Engineer")
    .release()
)
print(sorted(released), released["design_load"])
```

```text
blocked: 2 load-bearing value(s) are still drafts and nobody has confirmed them: ['bore_diameter', 'design_load']
['bore_diameter', 'design_load'] 50 kN
```

Confirmation is per value and names a person. Do not name yourself; ask the user who is
confirming, or report the values as unconfirmed.

## 6. Say what a screening result is

<!-- doctrine: screening-not-certified -->

A green scorecard means the closed-form checks Anvilate ran were satisfied by the inputs
it was given. It is not a certified analysis, not a substitute for a licensed engineer's
review, and not evidence that the part was tested.

The evidence bundle enforces the distinction rather than leaving it to prose: a bundle
carrying a verification plan with nothing performed is `NOT_EVALUATED` even when every
check passed, and `verified` is true only when a plan exists and every item in it has a
recorded, passing outcome.

```python
from anvilate.bundle import BundleSections
from anvilate.scorecard import Scorecard, ScorecardEntry

card = Scorecard(
    entries=(ScorecardEntry.from_safety_factor("pin bearing", computed=2.7, required=2.0),)
)
bundle = BundleSections(scorecard=card)
assert bundle.verified is False
print(bundle.summary())
```

```text
bundle PASS over 1 layer (checks); not covered: design basis, verification, review, exploration, callouts, load combinations, export, geometric tolerances; not test-verified
```

Report the bundle's own sentence, including what it does not cover. When you are asked
whether the part is good, the honest answer names the layers nobody has run.

## What you must not do

- Do not present a screening result as certified, stamped, or sealed analysis.
- Do not report a scorecard as passing while any check is `not_evaluated`.
- Do not substitute a recalled dimension for a database record that refused to resolve.
- Never make the confirmation decision for the user; ask who is confirming.
- Do not describe a check as citing a clause you did not read off the entry itself.

## Where to look next

Read `docs/` in the repository for the layer you are working in — `docs/citations.md` for
what a clause reference does and does not claim, `docs/evidence-bundle.md` for the
roll-up, `docs/repair-feedback.md` for the repair loop, and
`docs/quality-interchange.md` for handing results to quality software.
