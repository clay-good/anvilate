# Tasks: Expand open design data

## 1. Schema

- [ ] 1.1 Basis field (typical / A / B / spec-minimum) on strength properties, rendered
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
