# Calculation reports

A scorecard tells you a design passed. A calculation report shows the work: the
formula, the numbers put into it, the answer, and the clause it came from. That is
what a checker, an engineer of record, or a permitting jurisdiction actually
reviews, and it is what this page is about.

## What you get

```python
from anvilate.packs.structural import LiftingLug, screen_lifting_lug
from anvilate.report import CalculationReport, ReportSection
from anvilate.units import Quantity, UnitSystem

lug = LiftingLug(
    name="padeye",
    width=Quantity.parse("80 mm"),
    hole_diameter=Quantity.parse("25 mm"),
    thickness=Quantity.parse("12 mm"),
    load=Quantity.parse("50 kN"),
    material="ASTM-A36",
)
card = screen_lifting_lug(lug, required_safety_factor=2.0)

report = CalculationReport(
    title="Lifting padeye — screening calculations",
    project="Shop crane padeye, 50 kN",
    date="2026-07-27",                       # you supply it; the report never stamps itself
    unit_system=UnitSystem.SI,
    standards=("ASME BTH-1 — Design of Below-the-Hook Lifting Devices",),
    assumptions=("Static lift; no impact or side-load factor applied.",),
    sections=tuple(ReportSection(entry=entry) for entry in card.entries),
)

print(report.to_text())          # plain text
open("padeye.html", "w").write(report.to_html())   # a self-contained page
record = report.to_record()      # the same numbers, machine-readable
```

Each check renders as three lines and a glossary:

```
FAIL  padeye pin bearing
------------------------
    σ_p = P / (d · t)
    σ_p = 50.0 kN / (25.00 mm · 12.00 mm)
    σ_p = 166.7 MPa
  where:
    P = 50.0 kN  (lifted load)
    d = 25.00 mm  (pin hole diameter)
    t = 12.00 mm  (lug plate thickness)
    σ_p = 166.7 MPa  (pin bearing stress)
  safety factor 1.50 vs required minimum 2.00
  repair: increase thickness to 16 mm
  source: ASME BTH-1 §3-3
```

You never write those formulas. The check carries its own derivation, so the report
renders what was actually computed and cannot drift from it. A full working example
is [`examples/lifting_lug_calc_report.py`](../examples/lifting_lug_calc_report.py).

## What the document contains

In reading order: a header (project, preparer, date, unit system), the standards and
editions relied upon, the assumptions in force, one section per check, a margin
summary naming the governing check, and the screening disclaimer.

The **governing check** is the one running closest to its limit — the largest
required-over-computed ratio, not simply the lowest safety factor. A check at 3.0
against a required 4.0 governs over one at 2.0 against a required 2.5, and the
report says so, because that is the one that has to move first.

## What "screening" means

Every number here comes from a closed-form handbook or code formula, evaluated
exactly. That makes these calculations reproducible and checkable, and it makes them
*screening* calculations: they bound a problem and catch errors early. They are not
detailed analysis, they do not replace FEA where FEA is warranted, and they do not
constitute engineering sign-off. Every report carries that statement and it cannot
be switched off.

Where a formula needs a value from a copyrighted table — an allowable stress, a
chart-read coefficient — you supply it, and the report records it as user-supplied
alongside the clause that consumed it.

## Checks that have no derivation yet

A check that does not declare a derivation still appears. It renders its inputs,
verdict, and citation under a `derivation not rendered` label. So does a derivation
whose formula names a symbol it never supplies, because the substituted line would
otherwise show a bare symbol where a number belongs. The report never invents a
formula to fill the space — an honest gap is worth more to a reviewer than a
plausible fabrication.

Today the structural pack declares derivations for bending, shear and deflection;
the beam resonance check does not, and the industrial pack's cover-plate bending
declares one only for the circular closed-form cases — the rectangular, patch and
annular cases are series or numeric solutions, and they render an inputs table
rather than a tidy expression that is not what was computed.

## Handing it to a reviewer

The HTML is self-contained: no external stylesheets, scripts, fonts, or images, so
it opens on an air-gapped machine and survives being emailed. Rendering is pure
Python — no TeX, no browser, no network — and it is deterministic. The same inputs
produce byte-identical HTML on every rebuild, which means a diff between two reports
is an engineering change and never rendering noise.

## The calc record

`report.to_record()` returns a versioned JSON structure carrying every input,
symbolic form, substituted value, result, margin, and citation. It exists so a
firm's QA script can re-verify the numbers without parsing a rendered page. Values
are carried at full computed precision, not at display precision — the page may show
`1234.6 N` while the record holds `1234.56789`.

`report_from_record(record)` loads one back. A record whose schema major version this
build does not understand is rejected rather than misread.

## Current limits

- **PDF** is not implemented. HTML and text ship today; the PDF route is still open
  (see `openspec/changes/add-calculation-report/`).
- **Formulas render as plain text**, not MathML — readable, but not typeset.
Three limits that used to be listed here are closed, and the first mattered more than it
read:

- **Moments and second moments of area now follow the project's unit system** — N·mm
  and mm⁴ in SI, kip·in and in⁴ in US. N·mm is deliberately chosen over the more
  familiar N·m because it is *self-consistent with the section modulus*: the
  substituted line has to evaluate to the result printed under it, and
  `1500000.00 N·mm · 50.00 mm / 2100000.00 mm⁴ = 35.7 MPa` checks by hand while the
  same line in N·m came out a thousandfold short of its own stated answer. An author
  who wants a different unit for a particular symbol still pins it. Printed precision
  now widens for small values as well: a stress of 0.087 ksi used to print as `0.1 ksi`,
  a 15% error landing straight in the line a reviewer is told to check. The whole
  property — every substituted line evaluating to its own printed result — is asserted
  across every derivation the packs build, in both unit systems.
- **Areas follow the unit system too** (mm² / in²). Until an audit caught it, a
  US-system report printed `τ = 1.5 · 6.0 kN / 5000.00 mm²` above a result in ksi — SI
  force over SI area against a US stress, inside one equals sign.
- **Compound units read force-first** (`kip·in`, `N·m`) rather than the registry's
  alphabetical order. The reordering never changes, drops, or invents a factor: a
  label it cannot place — anything with a division, or two factors of the same kind —
  is passed through exactly as written.
