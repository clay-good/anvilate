# Tasks: Reviewable calculation reports

## 1. Contracts

- [x] 1.1 Design the derivation-metadata type (symbolic form, glossary, citation) and the
      registry keyed by check ID — `anvilate.derivation.Derivation` / `SymbolValue`, carried
      on the `ScorecardEntry` the check returns, so the work travels with the verdict
      instead of a side registry needing to be kept in sync
- [x] 1.2 Design the calc-record JSON schema (versioned) and its relationship to the
      scorecard and evidence roll-up — `CalculationReport.to_record()` /
      `report_from_record()`, `CALC_RECORD_SCHEMA_VERSION`
- [ ] 1.3 Decide the math-rendering route (HTML + MathML/MathJax-offline vs. drawn SVG)
      and the PDF backend (no TeX dependency) — HTML/text ship now with plain-text
      formulas; MathML and the PDF backend are still open

## 2. Implementation

- [x] 2.1 Derivation metadata for the initial slice of high-traffic checks, all in the
      structural pack: lug net tension and pin bearing, column buckling (Euler and
      Johnson, each showing the regime that actually governed), concrete bearing, bolt
      shear, plate bearing, edge tear-out (showing whichever of the two §J3.10 branches
      governed, not a `min()` the reader has to evaluate), bolt tension, combined
      tension+shear, weld throat shear, tension-member gross yielding and net rupture.
      Beam bending too: the beam checks now report the peak moment they already
      computed (`BeamBendingResult.max_moment`), so the flexure derivation reads the
      same for every support and load case while naming the case behind the moment.
      Still to wire: beam deflection and the per-case moment formulas behind it
      (w·L⁴/384EI and friends), base plate, gusset block shear, beam-column
      interaction, shear plate.
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
