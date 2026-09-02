# Change: Render a verdict line in the reader's units, not the units it was screened in

## Why

A calculation report that declares US-customary units prints this:

```
FAIL  rafter deflection
    δ = 5·w·L⁴/(384·E·I)
    δ = 5·0.0286 kip/in·(157.480 in)⁴/(384·29007.5 ksi·67.57 in⁴)
    δ = 0.117 in
  deflection 2.963 mm vs limit 16.000 mm
```

The work is in inches. The verdict under it is in millimetres. Same check, same document,
two systems — and the verdict is the line a reviewer reads first and the only one that
states the comparison the check actually made.

The substituted line above it was the same defect one layer down, and it is fixed: a
display-unit preference no longer overrides a declared system, and
`tests/test_rendered_lines.py` holds every line the packs build against the result printed
under it. This is the half that fix cannot reach, because a detail line is **a sentence
baked at screen time**, and the screen does not know what system the report will declare.

Four entry builders do it: the beam deflection screen, the frequency screen, a lifting
device's identification line, and a callout comparison. Every other verdict is derived from
`safety_factor` and `required_safety_factor` — numbers on the entry, rendered into a
sentence — which is exactly the shape the four are missing.

## What Changes

**A check that compares two quantities carries the two quantities.** `ScorecardEntry` gains
an optional structured comparison — what was measured, what it was judged against, and
which direction passes — and the report renders the sentence from it in the document's own
units. The baked `detail` stays as the fallback for every surface that has no system to
declare, so nothing that reads a scorecard today changes.

This is deliberately *not* "make `detail` a template". A sentence with holes in it is still
a sentence written in one place and read in another; what the report needs is the numbers.
The safety-factor path already proves the shape works — it produces the same sentence today
without any screen having written it.

## Impact

- Affected specs: `calculation-report`, by widening **Unit-system fidelity in
  derivations**. The requirement's name is kept because the archive matches on it, and it
  now understates its own scope: the property is about the document, not the derivation.
- Affected code: `anvilate.scorecard.ScorecardEntry`, the four builders, and
  `anvilate.report.document.ReportSection`.
- **The published scorecard schema moves.** An added optional property, so a client pinned
  to the current version reads a new document — but it is a contract change and carries a
  version with it.

## Open, and not a detail

**Does the comparison replace `detail` or sit beside it?** Beside it is additive and safe,
and leaves two statements of the same fact on one object where they can disagree — the
failure this repository has found in citations, in materials counts and in derivation
coverage, three times. Replacing it means every consumer of a scorecard reads a sentence
that no longer exists, including the CLI, the evidence bundle and the QIF export.

The safety-factor precedent argues for replacing: `from_safety_factor` writes the sentence
*from* the numbers at the moment the entry is built, so there is one source and the sentence
is a rendering of it. The same could be done here — build the sentence from the comparison
in the constructor — which keeps `detail` populated for every existing reader and makes it
derived rather than authored. That looks decisive and is the thing to decide before the
field is added, because a field every entry may set and four do is how a model accumulates.
