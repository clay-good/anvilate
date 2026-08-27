# Tasks: Expand open design data

## 1. Schema

- [x] 1.1 Basis field (typical / A / B / spec-minimum) on strength properties, rendered
      in reports
- [x] 1.2 Fatigue-record schema (curve parameters, conditions, specimen metadata,
      dataset provenance) — `anvilate.standards.fatigue`. Four required parts, two
      refusals, and the schema anchored against a curve the library already computes
      from the standard independently

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
      fetch recipe — the BUNDLED half is done (2026-08-27): every dataset under
      `standards/data` and `tolerance/data` declares name, version, source, an SPDX
      identifier on a redistributable allow-list, and an ISO retrieval date, enforced by
      `test_every_bundled_dataset_records_a_redistributable_license` with an adversary
      test beside it. The fetch-recipe half follows the importers in 2.2 and 2.4.
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

2.1-2.5 need external datasets (MIL-HDBK-5J, NIMS, the AISC xlsx) with fetch recipes and
license review, and 3.x needs a separate published repo.

## Shipped 2026-08-25 — task 1.2

`FatigueRecord` carries four parts and refuses to be built without any of them: the curve,
its survival level, the specimen it was measured on, and the dataset it came from.

**`CurveSurvival` is the fatigue analogue of `AllowableBasis`, and it bites harder.**
Design curves are drawn a stated number of standard deviations of log N below the mean, so
reading the mean as the design curve hands back exactly the margin that offset was there to
provide. A mean curve asked for a design answer returns `None` rather than the mean value
with a caveat somewhere.

**The specimen is required, because that is the half tables drop.** A polished
rotating-beam curve and a welded-joint curve are both "steel fatigue data" and neither
substitutes for the other. The stress ratio R is required in particular: the difference
between R = 0 and R = −1 is the whole subject of mean-stress correction. A welded-joint
curve that is genuinely R-independent says so with a flag; declaring both a flag and an R
is refused, because guessing which was meant would put a mean-stress correction on a curve
that already includes one.

**The curve declines outside its method's scope rather than extrapolating.** The
EN 1993-1-9 curve in this schema returns nothing below 10,000 cycles, where the standard
sends you to a strain-based assessment — while the bare formula in
`anvilate.analysis.fatigue` evaluates there quite happily. That difference is asserted as
deliberate in the tests, not left to be discovered.

**The anchor is a curve computed independently.** `en1993_detail_category_curve` expresses
the standard's two branches in this schema; `weld_detail_allowable_stress_range` computes
them straight from the standard, sharing no code. They agree to 1e-12 at forty
(category, life) pairs, which is evidence a fixture written alongside the schema could
never be.

**`model_copy` is overridden**, because pydantic runs no after-validator on a copy and
`curve.model_copy(update={"segments": ...})` was one call away from building the
discontinuous curve the constructor refuses.

**Audited an hour after shipping: three silent holes in one optional field.** The cutoff
stress range was checked only for not sitting above the end of the curve. `cutoff > last`
is False for NaN, so a NaN cutoff validated and the curve then answered NaN past its last
segment — a stress range that compares False against every limit it meets, so the check
consuming it passes. Zero and negative validated for the same reason and are worse for
being plausible: a cutoff of zero says every stress range survives forever. All three are
refused now.
