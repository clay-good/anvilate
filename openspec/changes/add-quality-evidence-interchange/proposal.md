# Change: Quality-data interchange — QIF results out, calibrated measurements in

## Why

Anvilate's scorecard is, structurally, a set of characteristics with evaluated actuals
against requirements — exactly what the quality/metrology world exchanges as QIF
(ISO 23952), whose schemas are free to implement
(https://qifstandards.org/download/). Exporting evidence as QIF Results makes Anvilate's
verdicts consumable by CMM and quality software at zero licensing cost — a bridge no OSS
design tool has.

In the other direction, the Digital Calibration Certificate (DCC) format (open PTB XSD
v3.3.0, https://gitlab.com/ptb/dcc/xsd-dcc/-/blob/master/dcc.xsd; accreditation bodies
began issuing digital symbols for signed machine-readable certificates in 2025) lets an
evidence chain terminate in a cryptographically signed traceable measurement — e.g., a
measured shaft diameter feeding an interference-fit check — extending provenance from
"standard table" to "calibrated instrument."

## What Changes

- `artifact-export` gains a requirement: export the scorecard/evidence as QIF Results
  with characteristics mapped from checks, citing ISO 23952.
- `input-ingestion` gains a requirement: accept DCC files as sources for measured input
  quantities, with the certificate's identity and (where present) signature status
  recorded in provenance.

## Impact

- Affected specs: `artifact-export` (1 added), `input-ingestion` (1 added).
- Affected code (when implemented): QIF serializer over the scorecard model; DCC XSD
  parser feeding the existing confirmed-input flow.
