# Tasks: Quality-data interchange

## 1. QIF export

- [x] 1.1 Check → characteristic mapping (requirement, actual, status, traceability)
- [x] 1.2 Serializer validating against the QIF schemas; unevaluated-characteristic
      handling — an unevaluated check crosses as `NOT_ANALYZED` carrying its requirement
      and no actual. Schema validation is opt-in (`ANVILATE_QIF_XSD` + `lxml`) because the
      schema package is a separate free download and the parser is not a runtime
      dependency; the test skips rather than passing when either is absent
- [x] 1.3 Round-trip test with a QIF-conformant reader — the suite's reader walks QIF's
      own structure (Characteristics → Items → Measurements by `CharacteristicItemId`),
      which is all a third-party product has to work with. A round trip through a specific
      commercial package is not runnable in CI and is not claimed here

## 2. DCC ingestion

- [ ] 2.1 DCC XSD parser (open PTB schema), value + uncertainty + certificate identity
- [ ] 2.2 Confirmation-flow integration and provenance record (issuer, id, signature
      status)
- [ ] 2.3 Uncertainty handoff to input distributions

## 3. Docs

- [ ] 3.1 Documentation: what QIF export contains; how to feed calibrated measurements in
      — the QIF half shipped as `docs/quality-interchange.md` with a worked example; the
      DCC half follows section 2
