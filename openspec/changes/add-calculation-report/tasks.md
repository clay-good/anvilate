# Tasks: Reviewable calculation reports

## 1. Contracts

- [ ] 1.1 Design the derivation-metadata type (symbolic form, glossary, citation) and the
      registry keyed by check ID
- [ ] 1.2 Design the calc-record JSON schema (versioned) and its relationship to the
      scorecard and evidence roll-up
- [ ] 1.3 Decide the math-rendering route (HTML + MathML/MathJax-offline vs. drawn SVG)
      and the PDF backend (no TeX dependency)

## 2. Implementation

- [ ] 2.1 Derivation metadata for an initial slice of high-traffic checks (beam bending,
      deflection, column buckling, bolt shear/tension, concrete bearing, lug limit states)
- [ ] 2.2 Tabular fallback rendering for checks without metadata, with the honest label
- [ ] 2.3 Document assembler: header, code editions, assumptions, per-check sections,
      margin summary with governing check, disclaimer
- [ ] 2.4 Calc-record emitter and round-trip loader
- [ ] 2.5 Determinism: byte-identical HTML across rebuilds (no timestamps, stable float
      formatting)

## 3. Tests & CI

- [ ] 3.1 Golden-file report tests for the initial check slice
- [ ] 3.2 Calc-record recompute test (external-verifier simulation)
- [ ] 3.3 CI coverage gate: new checks without derivation metadata fail unless registered
      tabular-only
- [ ] 3.4 Air-gapped render test (zero network calls)

## 4. Docs & examples

- [ ] 4.1 Example: lifting lug screening rendered to a submittal-shaped PDF
- [ ] 4.2 Documentation page: what the report contains, what "screening" means, how to
      hand it to a reviewer
