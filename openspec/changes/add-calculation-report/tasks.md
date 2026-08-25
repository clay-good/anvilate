# Tasks: Reviewable calculation reports

## 1. Contracts

- [x] 1.1 Design the derivation-metadata type (symbolic form, glossary, citation) and the
      registry keyed by check ID — `anvilate.derivation.Derivation` / `SymbolValue`, carried
      on the `ScorecardEntry` the check returns, so the work travels with the verdict
      instead of a side registry needing to be kept in sync
- [x] 1.2 Design the calc-record JSON schema (versioned) and its relationship to the
      scorecard and evidence roll-up — `CalculationReport.to_record()` /
      `report_from_record()`, `CALC_RECORD_SCHEMA_VERSION`
- [x] 1.3 Decide the math-rendering route (HTML + MathML/MathJax-offline vs. drawn SVG)
      and the PDF backend (no TeX dependency) — **MathML, laid out by the browser**
      (`anvilate.report.mathml`), and **no PDF backend: the HTML prints**. Both decisions
      turn on the same property, and section 6 records how they were checked

## 2. Implementation

- [x] 2.1 Derivation metadata for high-traffic checks. The structural pack is complete:
      every one of its checks carries a worked derivation — beam bending and transverse
      shear, column buckling, bolt shear/bearing/tear-out/tension/combined, weld throat,
      base-plate bearing and plate bending, lug tension and pin bearing, gusset block
      shear, tension-member gross yielding and net rupture, beam-column interaction,
      concrete bearing, and shear-plate yielding and rupture. Where a clause branches
      (§J3.10 tear-out, §H1.1 interaction, Euler vs Johnson) the derivation shows the
      branch that actually governed rather than a condition the reader has to resolve.
      Beam deflection too, for the eight standard full-span cases, which declare their
      closed form on the result (`BeamBendingResult.deflection_formula`). Off-default
      geometry (offset loads, patches, load pairs) solves numerically or through a
      series and declares none, so it falls back rather than showing a tidy formula
      that is not what was computed. The industrial pack's cover plate follows the same
      rule: the two circular uniform-pressure cases have exact closed forms and declare
      them, while the rectangular (Navier series), patch, and annular (numeric radius
      search) cases declare none.
- [x] 2.2 Tabular fallback rendering for checks without metadata, with the honest label
      ("derivation not rendered"; a derivation with undeclared symbols also falls back
      rather than printing a bare symbol where a value belongs)
- [x] 2.3 Document assembler: header, code editions, assumptions, per-check derivation
      sections, margin summary with governing check, disclaimer
- [x] 2.4 Calc-record emitter and round-trip loader (rejects an unreadable schema major;
      carries full precision, not display precision)
- [x] 2.5 Determinism: byte-identical HTML across rebuilds (no timestamps — the date is
      caller-supplied — and fixed float formatting)

## 3. Tests & CI

- [x] 3.1 Golden-file report tests for the initial check slice (`tests/test_report.py`
      asserts the exact rendered derivation lines)
- [x] 3.2 Calc-record recompute test (round trip plus a full-precision check that an
      external verifier reads the computed value, not the rounded one)
- [x] 3.3 CI coverage gate (`tests/test_contract.py`): the checks that declare a
      derivation are pinned so one cannot be dropped, every declared derivation must be
      fully substitutable (no bare symbol where a value belongs) and must cite a source.
      `derivation_coverage()` reports the worked/total ratio for a rendered report.
- [x] 3.4 Air-gapped render test (socket calls fail the test; HTML carries no external
      assets)

## 4. Docs & examples

- [x] 4.1 Example: lifting lug screening rendered to a submittal-shaped report
      (`examples/lifting_lug_calc_report.py`, HTML output; printing it is the PDF route — see 6)
- [x] 4.2 Documentation page: what the report contains, what "screening" means, how to
      hand it to a reviewer (`docs/calculation-reports.md`, with its code sample and
      quoted output verified against a real run)

## 5. Follow-ups surfaced while building

- [x] 5.1 Unit-system conventions for moments and second moments of area —
      `UnitSystem.moment_unit` (N·mm / kip·in) and `UnitSystem.second_moment_unit`
      (mm⁴ / in⁴), both wired into `_system_unit`. **The decision went to the
      self-consistent pair over the familiar one, and the reason turned out to be a
      correctness one, not a taste one:** a report's substituted line has to evaluate
      to the result printed under it, and `1500.00 m·N · 50.00 mm / 2100000.00 mm⁴`
      did not — it was short by a factor of a thousand against its own stated 35.7 MPa.
      In N·mm it checks by hand. The larger magnitudes are the price of arithmetic a
      reviewer can verify. Authors still pin a symbol's unit where they want another.
- [x] 5.2 Compound-unit ordering — `_engineering_order` reorders a pretty compound
      label force-first, then length, then as Pint gave it. It reorders factors and
      never changes, drops, or invents one: a label carrying a division, or one whose
      factors it cannot rank, is passed through verbatim, because a mangled label is
      worse than an unfamiliar one. The machine-readable (unpretty) label is untouched —
      spec cards echo it verbatim, so this is a document-rendering concern only.

## 6. The math-rendering and PDF decisions (1.3)

**MathML, because the air gap decides it.** MathML Core is laid out by the browser, so the
report stays one self-contained file with no script, no external font and no network — the
property the report's air-gapped render test already enforces. MathJax means bundling a
JavaScript engine into a document an engineer of record may seal. Drawn SVG means shipping
a layout engine and a math font inside this library. Both are larger commitments than
stacking a fraction is worth. The one honest caveat: MathML layout quality depends on a
math font being present (Windows ships Cambria Math, macOS 13+ ships STIX Two Math, per
MDN's MathML font guide); the markup is correct regardless, and bundling a font would break
the self-contained promise for a cosmetic gain.

**The renderer declines rather than guesses.** It parses the restricted grammar the
derivations are written in, writes the tree back out, and compares it to the input. A
mismatch falls back to the plain-text line — the same rule the derivation layer already
follows for a numerically solved result. CI typesets the whole declared corpus, so a
formula written outside the grammar fails the build rather than degrading quietly.

**The round trip is necessary and not sufficient, and the first draft proved it.**
Juxtaposition parsed at the same precedence as division read a substituted
`1.00 kN / 10.00 mm²` as `(1.00 kN / 10.00) · mm²` — a stress drawn as a force over a
number, times an area. The wrong tree writes back out as exactly the string it came from,
so the round trip passed it. **It was found by rendering a real report, not by a unit
test**, which is the whole argument for typesetting the corpus in CI rather than a handful
of examples.

**No PDF backend, and that is a decision rather than a deferral.** Every non-TeX route costs
either a browser dependency or a second math renderer. WeasyPrint — the obvious pure-Python
choice — does not support MathML (Kozea/WeasyPrint#59, still open) and runs no JavaScript,
so formulas would have to be pre-drawn as SVG by a separate tool: the drawn-SVG route
rejected above, re-entering through the back door and bringing Pango and cairo with it.
Headless Chromium renders MathML correctly, but it is the same browser already on the
reviewer's desk, and `Ctrl+P` from the HTML produces the typeset PDF today with nothing
added to this library. An unattended PDF is a shell out to a browser the caller already
chose, not a rendering backend this library owns.
