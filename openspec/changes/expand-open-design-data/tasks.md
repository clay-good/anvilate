# Tasks: Expand open design data

## 1. Schema

- [x] 1.1 Basis field (typical / A / B / spec-minimum) on strength properties, rendered
      in reports
- [ ] 1.2 Fatigue-record schema (curve parameters, conditions, specimen metadata,
      dataset provenance)

## 2. Data packs & importers

- [ ] 2.1 MIL-HDBK-5J-seeded allowables pack (curated slice; table citations;
      superseded note)
- [ ] 2.2 NIMS MatNavi fetch-on-first-use importer with documented registration step
- [ ] 2.3 CC-licensed fatigue dataset pack(s) with DOI provenance and license records
- [ ] 2.4 AISC shapes fetch-on-first-use importer (checksum, provenance, never bundled)
- [ ] 2.5 Bundled EN-profile open data with citations

## 3. Dataset publication

- [ ] 3.1 Standalone dataset repo/schema, versioning, contribution process
- [ ] 3.2 Anvilate consumes by pinned version; provenance records the pin

## 4. Tests & docs

- [ ] 4.1 License gate: every ingested source carries a recorded compatible license or
      fetch recipe
- [ ] 4.2 Named-section resolution tests (offline post-fetch; bundled EN data)
- [ ] 4.3 Docs: where each data class comes from, its basis, and its legal status

## Partially shipped 2026-08-22 — task 1.1

`AllowableBasis` (typical / specification minimum / B-basis / A-basis) on
`PropertyCitation`, `PropertyCitation.meets_basis`, `require_basis` raising
`InsufficientBasis`, the basis rendered in the provenance roll-up, and every bundled
strength classified from its own cited source with a gate that fails on a new record
without one. 8 of 17 materials carry specification minima, 9 carry typical values.

**The distinction was already in the database — as prose.** Some source strings said
"specified minimum" and some did not, so nothing could read it and a reviewer had to know
which handbook table was a mean and which was a minimum. Classifying per record rather
than in bulk found that two records citing the same book differ: Shigley's Table A-20 is
"Deterministic ASTM *Minimum* Tensile and Yield Strengths" and Table A-21 is "*Mean*
Mechanical Properties of Some Heat-Treated Steels". The classifying script was written to
FAIL on any source it could not justify, which is how the EN 755-2 record got read rather
than defaulted.

**Unclassified is not typical.** `None` satisfies no requirement, including the weakest,
so a record added without a basis fails a check that demands a minimum instead of passing
as though somebody had classified it.

Nothing else in this change is unblocked: 2.1-2.5 need external datasets (MIL-HDBK-5J,
NIMS, the AISC xlsx) with fetch recipes and license review, and 3.x needs a separate
published repo.
