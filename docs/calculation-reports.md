# Calculation reports

A scorecard tells you a design passed. A calculation report shows the work: the
formula, the numbers put into it, the answer, and the clause it came from. That is
what a checker, an engineer of record, or a permitting jurisdiction actually
reviews, and it is what this page is about.

## What you get

```python
from anvilate.packs.structural import LiftingLug, screen_lifting_lug
from anvilate.report import CalculationReport, ReportSection
from anvilate.spec import Provenanced
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
    assumptions=(Provenanced.stated("Static lift; no impact or side-load factor applied."),),
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
  repair: increase thickness to 16 mm — from the lug thickness inverse (σ ∝ 1/t, so SF ∝ t)
  source: ASME BTH-1 §3-3
```

You never write those formulas. The check carries its own derivation, so the report
renders what was actually computed and cannot drift from it. A full working example
is [`examples/lifting_lug_calc_report.py`](../examples/lifting_lug_calc_report.py).

## What the document contains

In reading order: a header (project, preparer, date, unit system), the standards and
editions relied upon, the assumptions in force, one section per check, a margin
summary naming the governing check, and the screening disclaimer.

**The standards and assumptions headings are always there, even when the list under one is
empty** — an empty list renders as `none declared`. It used to render as nothing at all,
which meant a report whose author deliberately declared no assumptions and one whose author
forgot the section were the same document to the reviewer it exists for.

**Every assumption carries who put it there.** An assumption is a `Provenanced` string,
so it renders with an origin tag — `[engineer stated]`, `[resolved from bundled data]`, or
`[library default: <reason>]` — and a defaulted one cannot be declared without the reason
it was chosen, because `Provenanced` already requires that. The field was a plain
`tuple[str, ...]` while the model's own docstring said "with their origin": an assumption
the engineer asserted and one the library supplied were the same bullet in a document
somebody signs. A bare string is refused rather than tagged with a guess, since defaulting
an untagged assumption to "engineer stated" would put a claim about provenance into a
signed document on nobody's authority.

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

## Checks that have no derivation

A check that does not declare a derivation still appears. It renders its inputs,
verdict, and citation under a `derivation not rendered` label. So does a derivation
whose formula names a symbol it never supplies, because the substituted line would
otherwise show a bare symbol where a number belongs. The report never invents a
formula to fill the space — an honest gap is worth more to a reviewer than a
plausible fabrication.

Some checks have no formula and never will. A Service Class 0 lifter is *exempt* from
fatigue analysis; the check states the exemption and computes nothing. Those say so on
themselves, in an `Underived` on the scorecard entry, and the reason prints beside the
label — `[derivation not rendered — Service Class 0 is the standard's own exemption…]`
— so a reviewer can tell "nothing is owed here" from "somebody still has to write this
down". Two kinds, and they are not the same:

| Kind | What it means |
| --- | --- |
| `lookup` | No arithmetic between the two numbers. An exemption, an identification line, a table comparison, a consistency verdict. |
| `numeric_result` | Real mathematics and no substitutable line: the value is the root of an equation, solved rather than evaluated, so the inputs table **is** its correct rendering. |

The declaration lives on the entry rather than in a file keyed by clause, because a
clause cited by two checks — one that computes and one that does not — cannot be
answered once.

What is left is **debt**: a closed form nobody has written down yet. Which clauses
those are is not left to prose. Every clause the library cites is counted on each test
run, and the run prints both ratios: **43 of 62 cited clauses fully worked, 44 of 62
fully answered** as of this writing. *Answered* means every entry citing the clause
either carries a derivation or states why it has none; a clause is not answered while
one entry is silent, because half a clause renders a formula for some parts and a bare
table for others, which reads as though all of it was derived.

The clauses still owing an answer are enumerated in
[`docs/api/underived-checks.txt`](api/underived-checks.txt):

| Section | What it means | Lines |
| --- | --- | --- |
| `[debt]` | A closed form nobody has written down yet. The list is downward-only. | 14 |
| `[lookup]` | What remains of the earlier design, in which every kind was keyed by clause. It does the same job for checks not yet given their own declaration; new ones go on the entry. | 4 |

Retiring a debt by calling it a lookup would convert unfinished work into a decision,
so the gate does not take the reason on trust. An entry carrying a computed **safety
factor** may not declare an absence of derivation at all — a safety factor is a
quotient and a quotient is a formula — and `ScorecardEntry` refuses to be constructed
that way, on a `model_copy` as well as on a call. Relabelling fails on the data, not on
the wording.

The gate is in `tests/conftest.py`. A new check that ships with neither a derivation nor
a stated reason fails the run by name; a debt that acquires one has to come off the
list; a listed clause nothing cites any more has to come off too. Checks that report
`NOT_EVALUATED` are outside the count — a check that could not run has no result to
show the work for.

## Handing it to a reviewer

The HTML is self-contained: no external stylesheets, scripts, fonts, or images, so
it opens on an air-gapped machine and survives being emailed. It also declares its own
surface — white paper, dark ink, `color-scheme: light` — because a document that names
a text colour and leaves the background to the viewer renders near-black on near-black
for a reviewer whose browser is in dark mode, which is a blank page rather than a
report. That was true here until someone opened one and looked. Rendering is pure
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

## Formulas are typeset, or they are not rendered at all

Formulas render as **MathML**: fractions stacked, radicals drawn, exponents raised. The
browser lays it out, so the report is still one file with no script, no external font and
no network — the same air-gap property the section above promises. MathJax would have meant
bundling a JavaScript engine into a document an engineer of record may seal; drawing the
math as SVG would have meant shipping a layout engine and a math font inside this library.
Both are larger commitments than stacking a fraction is worth.

**A formula that does not round-trip is not typeset.** The renderer parses the restricted
grammar the derivations are written in, writes the parse tree back out, and compares it to
the string it was given. A mismatch means the parse is not the formula the check cited, and
that line falls back to plain text — the same rule the derivation layer already follows for
a numerically solved result. Every derivation the library declares is typeset in CI, so a
new formula written outside the grammar fails the build where its author can see it rather
than quietly degrading in somebody's report.

**The round trip is necessary and it is not sufficient.** It catches a token dropped, added
or reordered. It cannot catch a precedence error, because the wrong tree writes back out as
exactly the string it came from — and one did: juxtaposition at the same precedence as
division read a substituted `1.00 kN / 10.00 mm²` as `(1.00 kN / 10.00) · mm²`, a stress
drawn as a force over a number times an area. What found it was rendering a real report, not
a unit test. That is the argument for typesetting the whole corpus in CI.

One caveat worth stating: MathML layout quality depends on a math font being present.
Windows ships Cambria Math and macOS 13+ ships STIX Two Math; elsewhere the glyphs may be
plainer. The markup is correct either way, and no font is bundled — a font in the document
would break the self-contained promise for a cosmetic gain.

## Print the HTML; there is no PDF backend

**Decided, not deferred.** Every non-TeX PDF route costs either a browser dependency or a
second math renderer, and the browser you would depend on is already on the reviewer's
desk. `Ctrl+P` from the HTML produces a PDF with the math typeset, today, with no
dependency added to this library.

What ruled out the obvious alternative: [WeasyPrint does not support
MathML](https://github.com/Kozea/WeasyPrint/issues/59), and it does not run JavaScript, so
the formulas would have to be pre-converted to SVG by a separate tool. That is the drawn-SVG
route rejected above, re-entering through the back door and bringing Pango and cairo with
it. Headless Chromium renders MathML correctly, but "install a browser" is a heavier ask
than "open the file and print", and it is the same browser either way.

If a PDF is needed unattended — a CI job attaching one to a release — that is a shell out to
a browser the caller already chose, not a rendering backend this library owns.

## Current limits

Five limits that used to be listed here are closed, and the first mattered more than it
read (the other two are the two sections above: formulas are typeset now, and the PDF
question is answered rather than open):

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
- **Section moduli and line loads follow it as well** (mm³ / in³, N/mm / kip/in), found
  the same way: an SI report printed `σ = M / Z = 169477.24 N·mm / 3.00 in³` and
  `M = wL²/8 = 100.00 lbf/ft · (3048.00 mm)² / 8`, every other factor converted and these
  two not. What holds all six families now is a gate that asserts the units *compose* —
  moment ÷ section modulus is exactly the stress unit, line load × length² is exactly the
  moment unit, each conversion factor exactly 1 — so choosing a spelling that does not
  compose fails rather than making every report unverifiable by its reader. Writing that
  gate corrected its own author: kN/m was going to be the example of a spelling out by a
  thousand, and 1 kN/m *is* 1 N/mm, so both compose and the choice between them is
  legibility. kN/mm is the one that really does not, and the gate catches it.
- **Compound units read force-first** (`kip·in`, `N·m`) rather than the registry's
  alphabetical order. The reordering never changes, drops, or invents a factor: a
  label it cannot place — anything with a division, or two factors of the same kind —
  is passed through exactly as written.
