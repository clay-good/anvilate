# Input Ingestion Specification (delta)

## ADDED Requirements

### Requirement: Calibrated measurements as input sources

The system SHALL accept Digital Calibration Certificate (DCC) files as sources for measured input quantities: parsed locally against the open schema, each offered value presented with its measurement uncertainty and certificate identity for the standard per-value confirmation flow; provenance for a confirmed value SHALL record the certificate identifier, issuer, and signature status, and a stated measurement uncertainty SHALL be available to the uncertainty-quantification capability as a typed input distribution.

#### Scenario: Measured shaft feeds a fit check

- **WHEN** the user supplies a DCC for a measured shaft diameter and confirms the value
- **THEN** the interference-fit check consumes the measured value with certificate provenance recorded, and the certificate's stated uncertainty is available as a declared input distribution

#### Scenario: Signature status is honest

- **WHEN** a DCC lacks a verifiable signature
- **THEN** the value is still usable after confirmation, with provenance plainly recording the unverified signature status — never silently presented as attested
