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

In reading order: a header (project, preparer, date, revision, unit system), the standards and
editions relied upon, the assumptions in force, one section per check, a margin
summary naming the governing check, the margin ledger, and the screening disclaimer.

**The margin ledger says how much of each margin was chosen.** `CalculationReport(margins=...)`
takes [margin ledger](margin-ledger.md) entries and renders them as a table of entry, kind,
value, quantity, origin and authority, then each quantity's cumulative factor with its
multiplication beside its code-required share, then any same-kind factors from two origins
as a possible double count with both origins named. A code-required factor and a
user-elected one with the same label render with different kinds, and the verdict never
reads the ledger. With no entries the heading stays and says `none declared`. The calc
record carries the entries from schema 1.2.

**A two-sided check shows its band in the Required column**, not just the floor:
`OVER MARGIN  6.67  2.00–4.00  net tension`. The column used to show the
minimum only, so an over-margin row read `6.67 vs 2.00 required` — the limit it satisfied,
while the 4.00 it exceeded appeared nowhere in the condensed table a reviewer actually
scans, and the row's verdict contradicted its own numbers. The band is shown whenever an
upper bound was declared, so what the column reports does not depend on which side of the
band the check landed.

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

Status comes first, though, in the card's own roll-up order: a failing check, then one that
could not run, then an over-engineered one, then the ratio above. See
[the governing check](repair-feedback.md#governing-check-and-governing-change) for the
ordering in full, including the one rung where the tie-break inverts.

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

## A margin summary with no margins in it

The condensed table at the foot of a report has a Safety factor column and a Required
column. Most checks on an ordinary document have neither: a material resolution, an
interface resolution, a classification, a tier that did not run. The rows stay, because a
check missing from the summary reads as one whose margin was not worth showing. This tool
reports what did not run rather than leaving it out.

The text form is a grid, as the HTML is, so an absent figure is an em dash under its
heading:

```text
Margin summary
--------------
  Result         Safety factor  Required     Check
  FAIL                    1.50   2.00        pin bearing
  PASS                  123.25   2.00        a much longer check name
  FAIL                    6.70  12.00–40.00  net tension
  WARNING                    —      —        material resolution
```

It used to be one sentence per check, `pin bearing: 1.50 vs 2.00 required`. That had two
faults. A row with no figures read `— vs — required`, comparing one absence with another.
And each figure followed a name of any length, so no two figures lined up on paper. In the
grid the figures align on the decimal point, which is what the calculation-report spec asks
of a printed summary. A test holds that alignment across figures of one to three digits and
a band.

## Checks that have no derivation

A check that does not declare a derivation still appears. It renders its inputs,
verdict, and citation under a `derivation not rendered` label. So does a derivation
whose formula names a symbol it never supplies, because the substituted line would
otherwise show a bare symbol where a number belongs. The report never invents a
formula to fill the space — an honest gap is worth more to a reviewer than a
plausible fabrication.

Some checks have no formula and never will. A Service Class 0 lifter is *exempt* from
fatigue analysis; the check states the exemption and computes nothing. Those say so on
themselves, in an `Underived` on the scorecard entry, and the label becomes the declaration
— `[no formula to render — a lookup, not a calculation: Service Class 0 is the standard's
own exemption…]` — so a reviewer can tell "nothing is owed here" from "somebody still has
to write this down" without reading to the end of the sentence. The kind opens the line
because the kind is what decides that; appending only the reason left every declared
absence still starting with the three words that mean work is missing. Two kinds, and they
are not the same:

| Kind | What it means |
| --- | --- |
| `lookup` | No arithmetic between the two numbers. An exemption, an identification line, a table comparison, a consistency verdict. |
| `numeric_result` | Real mathematics and no substitutable line: the value is the root of an equation, solved rather than evaluated, so the inputs table **is** its correct rendering. |

The declaration lives on the entry rather than in a file keyed by clause, because a
clause cited by two checks — one that computes and one that does not — cannot be
answered once.

What is left is **debt**: a closed form nobody has written down yet. Which clauses
those are is not left to prose. Every clause the library cites is counted on each test
run, and the run prints both ratios: **52 of 62 cited clauses fully worked, 62 of 62
fully answered** as of this writing. *Answered* means every entry citing the clause
either carries a derivation or states why it has none; a clause is not answered while
one entry is silent, because half a clause renders a formula for some parts and a bare
table for others, which reads as though all of it was derived.

The ratio counts **cited clauses**, and a card carries checks that cite nothing: the
screen's own material resolution, interface resolution, general tolerance class, load
classification and stack-up. Those were outside the count and outside the rule, and seven
of them said nothing at all — while `tolerance achievability`, written in the same module,
has carried its `lookup` declaration since the vocabulary existed. They all declare now,
and the property is stated over the card instead of over the citation: **every check that
reaches a verdict either shows its work or says why there is none.** `NOT_EVALUATED` is
deliberately outside it — a check that could not run is a gap, its `detail` line says what
stopped it, and making debt declarable is the collapse this vocabulary refuses.

That gate also pins the *wiring* rather than the function. `combination_derivation` is
called at exactly one place in the library, and making it return nothing — dropping the
worked calculation from the one check on a bracket's card that has one — passed the whole
suite before this property was stated.

Every clause is answered, so the debt list in
[`docs/api/underived-checks.txt`](api/underived-checks.txt) is empty:

| Section | What it means | Lines |
| --- | --- | --- |
| `[debt]` | A closed form nobody has written down yet. The heading is kept so a new one has somewhere obvious to go, and so the rules above it are in front of whoever writes the line. | 0 |

That file used to have a second section, `[lookup]`, which answered "this check has no
formula" per *citation*. It is gone. A clause cited by two checks — one that computes and
one that does not — cannot be answered once, and answering it once there was wrong for
every check but the first; every clause it held now has its `Underived` on the check
itself. A new check with no formula declares it on its entry, not in that file.

Retiring a debt by calling it a lookup would convert unfinished work into a decision,
so the gate does not take that reason on trust. An entry carrying a computed **safety
factor** may not call itself a lookup — a lookup asserts there is no arithmetic between
its two numbers, and a factor sitting between them disproves it — and `ScorecardEntry`
refuses to be constructed that way, on a `model_copy` as well as on a call.

`numeric_result` has no mechanical test, and deliberately not: a safety factor can itself
be solved rather than divided. A BS 7910 load-line margin is the scale at which a ray
crosses the Option 1 envelope, bisected for because the curve bends, and refusing every
declaration that sits beside a factor would refuse the one description that fits it.

The gate is in `tests/conftest.py`. A new check that ships with neither a derivation nor
a stated reason fails the run by name; a listed clause whose every entry has since
answered has to come off the list, and so does one nothing cites any more. Checks that report
`NOT_EVALUATED` are outside the count — a check that could not run has no result to
show the work for.

## Handing it to a reviewer

The HTML is self-contained: no external stylesheets, scripts, fonts, or images, so
it opens on an air-gapped machine and survives being emailed. It also declares its own
surface in both schemes: one token set defines a light and a dark ground and ink, and
each scheme sets them as a pair. A document that names a text colour and leaves the
background to the viewer renders near-black on near-black for a reviewer whose browser
is in dark mode, which is a blank page rather than a report. That was true here until
someone opened one and looked. Print is always black on white.

The page is restrained by a gate, not by taste:

| Rule | What the test in `tests/test_report.py` checks |
| --- | --- |
| Enumerated vocabulary | Every element a report renders, and every tag the renderer writes, is on a fixed list of prose, table and MathML elements. The stylesheet uses only listed properties, with no gradient, shadow, image or animation. |
| One accent | A single accent colour draws the keyboard focus outline and nothing else. |
| Status colours carry status | Each status colour appears only on its own status word, and every other token is a neutral grey. |
| Contrast, both ways | In each scheme, ink reaches 7:1 and every status word 4.5:1 against its ground, and the focus outline reaches 3:1. The status words, ink and accent also stay ΔE ≥ 20 apart under three simulated colour-vision deficiencies. |

Rendering is pure
Python — no TeX, no browser, no network — and it is deterministic. The same inputs
produce byte-identical HTML on every rebuild, which means a diff between two reports
is an engineering change and never rendering noise. The unit renderer owns its document
glyphs rather than accepting whatever a Pint release happens to choose: multiplication is
always `·`, the micro prefix is always `µ`, and engineering moments remain force-first.

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

**The symbol legend is typeset too, and it was not.** The working rendered `σ_b` as a
subscript and the glossary row beneath it printed the literal string `σ_b` — two spellings of
one symbol in one document, in every legend row whose symbol carries a subscript. Matching a
symbol in the working to its row in the legend is the thing a reviewer actually does with that
table, so the cells carry the same MathML the formula does, at `display="inline"`. Any symbol
the grammar declines is escaped and printed as text, by the same rule the formula lines
follow: a legend entry that is not the symbol the check cited is worse than a line of text.
The plain-text rendering is untouched, and there the raw `σ_b` is right, because the formula
beside it is raw too — each rendering is internally consistent, which is the property that
matters.

Found the same way the precedence bug was: by rendering a report and looking at it.

One caveat worth stating: MathML layout quality depends on a math font being present.
Windows ships Cambria Math and macOS 13+ ships STIX Two Math; elsewhere the glyphs may be
plainer. The markup is correct either way, and no font is bundled — a font in the document
would break the self-contained promise for a cosmetic gain.

## A PDF for the submittal, the HTML for typeset math

`report.to_pdf()` returns the report as PDF bytes. It is the text form typeset for paper,
so a formula reads `σ_p = P / (d · t)` as it does in the terminal, not as typeset math.

```python
open("padeye.pdf", "wb").write(report.to_pdf())
```

| Print rule | How the PDF keeps it |
| --- | --- |
| Byte-identical on reissue | Nothing reads the clock, objects are numbered in document order, and no stream is compressed, so no compressor version can change the bytes. Only a change to the report changes the file. |
| A derivation is never split | A check's section is one block. A block that does not fit on the rest of a page moves to the next one whole. |
| Continued tables repeat their headers | A block longer than a page repeats its heading, marked "(continued)", at the top of each page it runs onto. |
| Values align on the decimal | The page is set in Courier, one cell per character, so every column the text form lines up is lined up on paper too. |
| Nothing depends on colour | No content stream sets a colour. The status words carry the verdict. |
| Page furniture | Every page carries the title, the project and `revision`, the date and "page N of M". |

**No font is embedded, and no character is lost.** Courier and Symbol are two of the
fourteen fonts every PDF reader carries. Some characters the package writes are in
neither: the GD&T symbols, ≲ and ≪, subscript letters, circled modifiers, and ṁ. Each of
these is drawn as a vector glyph in a Type 3 font inside the file. The glyph is composed
from Courier and Symbol where it can be, and drawn as a path where it cannot. A ToUnicode
map lets the text layer read back as the characters themselves, so search, copy and a
screen reader all get `σ`, not a glyph number. A character this package has never
written is printed as an empty box, and it still reads back as itself.
`tests/test_report_pdf.py` reads every PDF back with pdfminer, an independent parser. It
requires every character in the package's own strings to have a real glyph, and it holds
each print rule above.

**For typeset math, print the HTML.** The HTML report typesets formulas in MathML. A
browser's print dialog turns that into a PDF with the math set properly. That PDF is not
byte-identical, because a browser stamps the date into it. Use `to_pdf()` for a submittal
that will be reissued and compared. Use the browser when the math has to look typeset.

## A rendering change is a reviewed change

Nine reference reports are rendered as text, HTML and PDF, and each rendering is compared
with a copy committed under `tests/renderings/`. Between them they reach every status and
every optional block. A change to anything a reviewer would see fails the suite with the
difference shown. That includes a reworded label, a changed glyph and a new page break. If
the change is meant, regenerate the copies and commit them, so the change is reviewed in
the diff:

```bash
ANVILATE_ACCEPT_RENDERINGS=1 pytest tests/test_renderings.py
```

## Current limits

**A declared unit system does not reach every discipline.** The mechanical and structural
families follow it completely — lengths, forces, stresses, moments, second moments, areas,
section moduli and line loads all convert, and every substituted line evaluates to its own
printed result in both systems. Three families do not, and say so rather than mixing:
a ventilation zone's outdoor-air requirement stays in L/s and m², and an air-change rate in
m³/hour, whatever the document declares.

The reason is that the system's table holds **one unit per dimension**, and two disciplines
want different ones. `area_unit` is mm² because a structural section modulus divides by it;
a flow per square millimetre is not a unit anybody writes. Where a pack's units are
arithmetic rather than taste — the sum only adds up in that set — the symbol says so and
keeps them, which is visible in the document rather than silent. A US-customary ventilation
report is therefore in SI, and that is a gap rather than a decision: closing it means a
per-system required unit, which nothing has asked for yet.


Five limits that used to be listed here are closed, and the first mattered more than it
read (the other two are the two sections above: formulas are typeset now, and the report
prints to PDF):

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
  across **every derivation the suite builds**, in both unit systems: roughly 1,900
  distinct lines, read off the same session-wide collector the derivation-coverage and
  effectivity ratchets read. It used to run over a hand-written sample of about 100 cards,
  and the difference was not academic. Four things were wrong in the 1,800 the sample could
  not see: the deflection lines all evaluated 1.73× low, because pint drops a radical
  written over a bare number and read `9·√3` as 27; a `min(1, …)` line came back in
  *minutes*, because `min` is a unit to pint; three checks declared a **signed** demand
  while their arithmetic divides by its magnitude, so a hogging member's interaction line
  read `8/9 · −17.70 kip·in / 46.10 kip·in` beside a printed 0.840 and works out to 0.158;
  and four checks that were *not evaluated* carried a derivation anyway, printing a result
  of 0.0 over a line reading `n = F / 0`. A check that could not run now carries no worked
  line at all.
- **Every derivation the suite builds is typeset, not a sample of them.** The same widening,
  applied to the MathML renderer: 2,656 distinct lines. Sixteen were being declined and
  rendered as plain text in a submittal document, in three families whose *exponent or
  operator is the whole point* — the Direct Strength Method's `(P_crd/P_y)^0.6`, the
  aluminium weld-affected blend `F_c^(1/3)·F_e^(2/3)`, and the Marin surface factor
  `min(1, 4.51·S_u^-0.265)`. The grammar took `**` and the superscript digits and not the
  caret, and read `min` as three italic letters. Both are in it now, and a caret is not
  normalised to `**`: the round trip compares the tree written back out against the author's
  own string, so the spelling has to survive.
- **The tolerance is read off the line, not guessed.** The comparison used to allow a flat
  1%, described as the result's last place plus slack for the inputs' own rounding — and it
  was not that, it was a number that happened to cover the corpus. A line that *cubes* a
  printed length does not stay inside it: a 4 mm spring wire prints as `0.157 in`, three
  significant figures, and cubed that is a 1.1% error before anything else in the line
  rounds, so the gate reported a mismatch on a line that was right. Each printed **quantity**
  now contributes half its last place relative to itself, times whatever exponent stands on
  it. A bare decimal is a coefficient the formula states — a load factor, a Poisson ratio,
  an exponent — and it is exact; counting those as rounded handed an ASCE load combination
  37% of tolerance off nothing but its own factors. Across 1,976 lines the widest tolerance
  any line earns today is 1.5%, and a line that buys more than 3% fails: either the model
  has started over-counting again, or the report is printing too few figures for a reviewer
  to check the line at all.
- **Scientific notation is one number, and it used to typeset as an addition.** A bearing's
  rating life prints its required revolutions as `1.74e+09`; the renderer read `1.74e` as a
  number, `+` as an operator and `09` as another, so the report showed a fraction divided by
  1.74e *with 09 added to it*. **The round-trip guard could not see it** — the wrong tree
  writes back out as exactly the string it came from — so it took rendering the page and
  looking at it. It reads as `1.74 × 10⁹` now, and the sweep fails any line that typesets a
  number token carrying a letter.
- **An enum's value is a machine spelling, like a unit's.** `units.unit_label` exists
  because a repair hint printed `4000 mm**2` in a document a reviewer signs; sixteen
  rendered descriptions read "peak bending moment, fixed_fixed beam under point load", and a
  material-basis refusal read "AISI-4140 yield_strength is typical … and
  specification_minimum was required". `units.spoken` is the fix, and it takes the separator
  rather than choosing one: a beam support is a compound adjective and takes a hyphen
  (*fixed-pinned*), a property or a basis is a noun phrase and takes a space (*yield
  strength*), and nothing in the string says which. The sweep resolves against the enums the
  package actually declares, so a field name a diagnostic is quoting back is not a finding
  and a new enum is covered the day it ships.
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
