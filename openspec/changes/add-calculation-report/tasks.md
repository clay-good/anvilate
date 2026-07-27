# Tasks: Reviewable calculation reports

## 1. Contracts

- [x] 1.1 Design the derivation-metadata type (symbolic form, glossary, citation) and the
      registry keyed by check ID — `anvilate.report.Derivation` / `SymbolValue`; sections
      bind a derivation to its scorecard entry (a per-check-ID registry lands with 2.1)
- [x] 1.2 Design the calc-record JSON schema (versioned) and its relationship to the
      scorecard and evidence roll-up — `CalculationReport.to_record()` /
      `report_from_record()`, `CALC_RECORD_SCHEMA_VERSION`
- [ ] 1.3 Decide the math-rendering route (HTML + MathML/MathJax-offline vs. drawn SVG)
      and the PDF backend (no TeX dependency) — HTML/text ship now with plain-text
      formulas; MathML and the PDF backend are still open

## 2. Implementation

- [ ] 2.1 Derivation metadata for an initial slice of high-traffic checks (beam bending,
      deflection, column buckling, bolt shear/tension, concrete bearing, lug limit states)
      — lug tension + pin bearing done in the example; the rest still to move into the packs
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
- [ ] 3.3 CI coverage gate: new checks without derivation metadata fail unless registered
      tabular-only — `derivation_coverage()` reports the ratio; the gate lands with 2.1
- [x] 3.4 Air-gapped render test (socket calls fail the test; HTML carries no external
      assets)

## 4. Docs & examples

- [x] 4.1 Example: lifting lug screening rendered to a submittal-shaped report
      (`examples/lifting_lug_calc_report.py`, HTML output; PDF pending 1.3)
- [ ] 4.2 Documentation page: what the report contains, what "screening" means, how to
      hand it to a reviewer

## 5. Follow-ups surfaced while building

- [ ] 5.1 Unit-system conventions for moments and second moments of area. `_system_unit`
      maps force, length, stress, and mass only, so a bending derivation in a US project
      leaves `M` in N·m and `I` in mm⁴ while lengths convert to inches. Deliberately not
      invented here: picking N·mm/kip·in (self-consistent with mm⁴/in⁴ and MPa/ksi) over
      the more familiar N·m/kip·ft is a units-capability decision. Authors can pin a
      symbol's unit explicitly in the meantime.
- [ ] 5.2 Compound-unit ordering. Pint prints factors alphabetically ("in·kip", "m·N")
      rather than the force-first engineering convention ("kip·in", "N·m"). Values are
      correct; only the label order reads oddly in a submittal.
