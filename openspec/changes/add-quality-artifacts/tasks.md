# Tasks: Quality artifacts

## 1. FMEA

- [x] 1.1 FMEA row generation from functions, failure-mode catalog, card checks and
      verification items (`anvilate.fmea`; the spec's bracket scenario runs on a team
      catalogue, since the shipped one holds no bend-fatigue or bearing-yield mode)
- [x] 1.2 Anvilate's published occurrence and detection scales, with their derivation
- [x] 1.3 Loading of user rating tables and action-priority matrices, with source; no
      licensed table shipped (gated by a test over the bundled data)

## 2. Characteristics

- [x] 2.1 Critical and significant marks with symbol and reason on dimensions,
      tolerances, properties
- [x] 2.2 Marks carried to drawings, QIF, inspection plan, control-plan seed
      (the drawing balloons the callout with the characteristic's number and the
      customer's symbol; QIF writes a `CharacteristicDesignator` with the number and the
      criticality, schema-validated against the published QIF 3.0 XSD. `critical` uses
      the schema's CRITICAL enum member; `significant` goes through `OtherLevel` rather
      than borrowing MAJOR or KEY, which are other schemes' tiers)
- [x] 2.3 Stable characteristic numbering across revisions; accountability table

## 3. Plans and records

- [x] 3.1 DVP&R export of the verification plan
      (CSV and XLSX, one row per item; no archetype routes a fatigue check yet, so the
      spec scenario's durability row waits on a durability archetype)
- [x] 3.2 Control-plan seed export
- [x] 3.3 Risk records (ISO 14971 / ISO 12100 structure) with linked controls

## 4. Traceability

- [x] 4.1 Trace from requirement to evidence; uncovered and untraced markers
      (`anvilate.trace`, as CSV and ReqIF)
- [x] 4.2 ReqIF export, schema-validated against the published ReqIF XSD
      (validated locally and in CI's scheduled interchange job, by xmlschema, which
      fetches the XHTML modules the schema includes)
- [x] 4.3 A docs page for quality artifacts: which industry form each export feeds, and
      what stays with the user's QMS
      (written for the DVP&R and the trace; it grows with each export)
