# Artifact Export Specification (delta)

## MODIFIED Requirements

### Requirement: Evidence bundle

Every validated export SHALL include an evidence bundle (HTML, optionally PDF) containing: the spec, the scorecard with thresholds and measured values, FEA assumptions and stress-field imagery, mesh statistics and convergence history, material and standards data provenance, solver and kernel versions, the exact solver input decks, and the iteration history — sufficient for an independent engineer to reproduce the run.

The bundle's rendered form SHALL name **each check individually**, with its detail and the clause it cites, rather than a count of how many ran. A roll-up over layers is a legitimate document — the attestation predicate carries one — but it is not the document handed to a reviewer, and a surface that emits it under the name "evidence bundle" is emitting a verdict rather than evidence.

#### Scenario: Reproducibility from the bundle

- **WHEN** a senior engineer receives only the evidence bundle and the Anvilate release named in it
- **THEN** they can re-run the identical analysis and obtain the same scorecard

#### Scenario: Screening label on the bundle

- **WHEN** any evidence bundle is generated
- **THEN** it carries the non-dismissable screening-analysis disclaimer and the list of modeling assumptions

#### Scenario: Every check is named, not counted

- **WHEN** a bundle is rendered for a card on which one check failed
- **THEN** the document names that check, its detail and its citation, so a reviewer can see which one failed and against what — rather than only that one of several did
