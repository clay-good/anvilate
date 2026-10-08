# Tasks: Expand open design data

## 1. Schema

- [x] 1.1 Basis field (typical / A / B / spec-minimum) on strength properties, rendered
      in reports
- [x] 1.2 Fatigue-record schema (curve parameters, conditions, specimen metadata,
      dataset provenance) — `anvilate.standards.fatigue`. Four required parts, two
      refusals, and the schema anchored against a curve the library already computes
      from the standard independently

## 2. Data packs & importers

- [x] 2.1 MIL-HDBK-5J-seeded allowables pack (curated slice; table citations;
      superseded note) — `standards/data/mil_hdbk_5j.yaml`, eight records in the default
      database: 2024-T3 sheet, 2024-T351 plate, 7075-T6 sheet and 7075-T651 plate, each at
      A- and B-basis, from Tables 3.2.3.0(b1) and 3.7.6.0(b1). A screen on one states the basis,
      table and superseded note on every entry; the provenance trail carries the note too
- [ ] 2.2 NIMS MatNavi fetch-on-first-use importer with documented registration step —
      BLOCKED on the format, not the fetch: `anvilate.fetch` already does consented,
      digest-pinned downloads, but MatNavi's fatigue sheets sit behind a per-user
      registration, and no sample of their export is available without one. An importer
      written without a real file to parse would be a parser of a guessed format. Ship it
      when a registered user supplies one export, with its terms of use, to pin against
- [x] 2.3 CC-licensed fatigue dataset pack(s) with DOI provenance and license records —
      shipped 2026-10-08 as `standards/data/weld_fatigue.yaml` + `standards.weld_fatigue`:
      two campaigns from "A Dataset of Fatigue Properties for Welded Joints" (Deng et al.,
      figshare 2025, v2, CC BY 4.0, DOI 10.6084/m9.figshare.29254265.v2), copied point for
      point from its S-N.json (md5 55a9defc400f717147702d6c8a91f0ce) — SM50B cruciform,
      axial, R = 0, 23 °C air, 20 mm, 38 failures (dataset_id 1868); 6082-T6 FSW butt,
      axial, R = 0.1, 25 °C air, 3 mm, 19 failures (dataset_id 2022); then 2024-T4 FSW
      (4636) and aged AM Scalmalloy FSW (3387), with their run-outs kept and unfitted;
      ultrasonic (~20 kHz) campaigns were excluded. A campaign was
      bundled only where the release states temperature (as a number), environment, R and
      thickness; "ambient" was not read as 20 °C, and a series sharing its metadata with a
      sibling from the same paper was left out. Each record is a MEAN curve fitted by ASTM
      E739 least squares (log N on log Δσ) over the tested range only, cites the dataset DOI
      and the campaign's original paper (`DatasetProvenance.publication`), and declines a
      design-curve request; the fit is held to `statistics.linear_regression` and to numpy's
      polyfit values (tests/test_weld_fatigue.py). Consumer (b4f1fcc4):
      `FatigueRecord.check(...)` cites the dataset and says "test-data-backed ... curve
      through N specimens". The spec's "replaces an estimate" scenario has no estimate to
      replace yet: no material-keyed fatigue screen with an FKM-estimated curve exists, so
      that half waits on one. The FABEST candidate below stays blocked
      on its missing test temperature and environment. Earlier note: the FABEST database
      (42CrMo4+QT, CC BY
      4.0, DOI 10.5281/zenodo.20967342, md5 9e116aa634fe72c166e6790469788d37) carries a
      Basquin fit per campaign, N = C·S^-w on stress amplitude. Refitting FAB001 (axial,
      R = -1, turned unnotched bar, 9 broken specimens, 3,169-514,828 cycles) by least squares
      of log N on log S reproduces w = 12.305237 and C = 8.641290e38 exactly, and the
      workbook's own 572.660 MPa at 1e5 cycles. **Blocked on the specimen, not the curve:**
      neither the workbook, the Zenodo records nor the HCF participant package states a test
      temperature or environment, and `SpecimenMetadata` requires both. The cited paper
      (Int. J. Fatigue 2023, 107743) is behind a paywall. Ship it when a source states them,
      not by writing "room temperature" in
- [x] 2.4 AISC shapes fetch-on-first-use importer — the v16.0 publisher workbook is pinned
      by SHA-256 and fetched only after explicit consent. Its W-shape geometry is parsed into
      cited sections from the verified local cache; provenance travels into evidence, and the
      existing release-content gate ensures the non-redistributable workbook never ships
      (`standards/profiles.py`, `tests/test_profiles.py`)
- [x] 2.5 Bundled EN-profile open data with citations — `standards/data/en_profiles.yaml`:
      the 42 EN 10365 IPE and HEA profiles as dimensions, CC0, each cited; properties computed
      with the root fillets and held to the published tabulations (tests/test_profiles.py)

## 3. Dataset publication

- [ ] 3.1 Standalone dataset repo/schema, versioning, contribution process
- [ ] 3.2 Anvilate consumes by pinned version; provenance records the pin

## 4. Tests & docs

- [x] 4.1 License gate: every ingested source carries a recorded compatible license or
      fetch recipe — BOTH halves now (2026-08-27). The bundled half:: every dataset under
      `standards/data` and `tolerance/data` declares name, version, source, an SPDX
      identifier on a redistributable allow-list, and an ISO retrieval date, enforced by
      `test_every_bundled_dataset_records_a_redistributable_license` with an adversary
      test beside it. The fetch half: `anvilate.fetch` implements the standards-data
      requirement the importers in 2.2/2.4 were waiting on — a `DatasetRecipe` carrying
      the URL, digest, SPDX licence and whether it is redistributable at all; consent as
      an argument rather than a default; the digest verified on download *and* on every
      read; a provenance sidecar the cache is self-describing from; and the retrieval date
      stated by the caller, since nothing in the package may read the clock. The transport
      is injectable, so the whole flow is tested offline.
- [x] 4.2 Named-section resolution tests (offline post-fetch; bundled EN data) — both routes
      screen as the equivalent declared section and record their source. `section: IPE 200`
      uses the bundled EN table; after one consented fetch, `section: W12x26` uses the verified
      local AISC cache without touching the network (`tests/test_profiles.py`)
- [x] 4.3 Docs: where each data class comes from, its basis, and its legal status —
      `docs/citations.md`, completed 2026-08-28. The three classes are each answered on
      that page: the **bundled** tables now by name rather than by count, in a table whose
      every cell (source, version, SPDX identifier, retrieval date) is read back out of the
      dataset blocks by `test_the_dataset_table_is_the_datasets_own_metadata` — in both
      directions, since a row for a file that no longer ships is as wrong as a shipped file
      with no row; the **fetched** class by the `anvilate.fetch` section, which states that
      what ships is the recipe and the digest and never the payload; and the **basis** by
      the allowable-basis and fatigue-survival sections, which say what a value covers and
      what refusing to answer looks like. A count was the weakest true thing the page could
      say about seventeen files — it survives a version bump, a changed licence, and one
      dataset swapped for another.

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

## Shipped 2026-09-25 — task 2.1

**The source is the last public edition, and it says so.** MIL-HDBK-5J (31 January 2003) is
a US Government work under Distribution Statement A. MMPDS replaced it and is not free.
`PropertyCitation.superseded` carries that fact. It is filled from the dataset block into
every citation, so a screen's entries and the evidence bundle's provenance both say it. The
field is optional and no other dataset sets it, so every other rendering is unchanged.

**Transcription was checked against the table layout, not by eye.** Table 3.2.3.0(b1) has
20 value columns and Table 3.7.6.0(b1) has 21. Each L-direction row was counted to that
width before a value was taken from its column. The test pins the values the handbook
prints, not the file's own.

**Passing entries now state a statistical basis.** `design_allowable` used to disclose only
a relaxed basis. An A- or B-basis value now names its basis, table and condition on every
entry. A specification minimum still adds nothing, so the existing cards read as before.
The README's basis-split gate now counts `meets_basis(SPECIFICATION_MINIMUM)`, the question
the default gate actually asks; counting only the literal minimum would have reported the
pack as typical.

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
