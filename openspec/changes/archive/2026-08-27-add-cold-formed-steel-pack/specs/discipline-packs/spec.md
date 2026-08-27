# Discipline Packs Specification (delta)

## ADDED Requirements

### Requirement: Cold-formed steel pack

The cold-formed steel pack SHALL provide, when shipped: Direct Strength Method member screens for compression and flexure covering local, distortional, and global limit states per the cited AISI S100 sections and edition; elastic buckling loads and moments SHALL be typed inputs with declared provenance — user-supplied or computed by an external finite-strip tool whose identity and version are recorded — and the pack MUST NOT estimate buckling values internally; the governing limit state SHALL be identified in every result.

#### Scenario: DSM column screened from finite-strip inputs

- **WHEN** a lipped-channel column is screened with elastic buckling values computed by an external finite-strip tool and supplied with tool provenance
- **THEN** the compression screens report local, distortional, and global strengths per the cited sections, identify the governing limit state, and record the buckling-value provenance

#### Scenario: Buckling values never invented

- **WHEN** a DSM screen runs without elastic buckling inputs
- **THEN** the check reports not evaluated naming the missing inputs and the accepted sources (user-supplied or a supported external tool), rather than approximating

#### Scenario: Prequalification boundary stated

- **WHEN** a screened section falls outside the method's prequalified geometric limits declared to the check
- **THEN** the result carries a warning naming the exceeded limit, and the report states the applicable resistance-factor consequence per the cited section
