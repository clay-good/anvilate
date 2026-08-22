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

- [x] 2.1 DCC XSD parser (open PTB schema), value + uncertainty + certificate identity —
      DCC v3.3.0 over D-SI v2.2.1. The D-SI unit vocabulary is a declared table, because
      the published schema types a unit as an open string: an unknown token is recorded as
      a value not taken, naming the token, never resolved to something plausible
- [x] 2.2 Confirmation-flow integration and provenance record (issuer, id, signature
      status) — `SignatureStatus` has two members and no `VERIFIED`: verifying an XML
      signature needs a trust anchor an offline tool does not have, so a certificate is
      unsigned or signed-and-unchecked, and the laboratory's own seal flag is carried
      separately as a claim
- [x] 2.3 Uncertainty handoff to input distributions — an expanded uncertainty *U* at
      coverage factor *k* becomes `Symmetric(half_width=U, sigma_level=k)`; a certificate
      that states no usable *k*, or declares a non-Gaussian distribution, hands over
      nothing and says why

## 3. Docs

- [x] 3.1 Documentation: what QIF export contains; how to feed calibrated measurements in
      — `docs/quality-interchange.md`, with a worked example in each direction
