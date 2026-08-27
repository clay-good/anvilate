# evidence-attestation Specification

## Purpose
Sealing a finished evidence bundle so somebody else can tell what it covers and whether it moved. The bundle is content-addressed — the same inputs rebuild the same digest, and a materials-database bump visibly does not — wrapped in a standard attestation envelope, and carries both a software bill of materials and a machine-readable statement of where AI was involved. Signing is optional and offline: an unsigned bundle says it is unsigned and a signature nobody checked is reported as unverified, never as verified.

## Requirements
### Requirement: Content-addressed evidence identity

Every evidence bundle SHALL carry a content-addressed identity: a digest computed over the spec document, the toolchain version set, the standards/materials database versions, and the produced artifacts; artifact writers SHALL be byte-deterministic (no embedded timestamps or unstable float formatting) so that identical inputs reproduce the identical digest.

#### Scenario: Rebuild is a cache hit

- **WHEN** the same spec is rebuilt with identical toolchain and database versions
- **THEN** the evidence bundle digest is identical, and any digest change is attributable to a real input change

#### Scenario: Drift is visible as a hash change

- **WHEN** a standards-database version bump changes a resolved dimension
- **THEN** the bundle digest changes and the provenance graph identifies the changed input

### Requirement: Standard attestation envelope

The evidence bundle SHALL be expressible as an in-toto attestation: subjects are the digests of the produced artifacts, and the predicate (a versioned, documented Anvilate predicate type) carries the scorecard, citations, provenance graph, and toolchain versions; the predicate schema SHALL be published and versioned.

#### Scenario: Standard tooling reads the claim

- **WHEN** an attestation is produced for a validated part
- **THEN** standard in-toto/attestation tooling can parse the envelope, identify the subject artifacts by digest, and read the Anvilate predicate against its published schema

### Requirement: Optional signing with offline verification

Attestations SHALL be signable — keyless in CI (Sigstore-class) or with a user-held key locally — and Anvilate SHALL provide a verification command that checks signature, subject digests, and predicate schema; signing MUST be optional, air-gapped mode SHALL support local-key signing or unsigned bundles with the unsigned state plainly recorded, and verification of a signed bundle SHALL be possible offline given the bundle and public material.

#### Scenario: CI signs, engineer verifies

- **WHEN** a CI build signs an attestation and an engineer later runs the verification command on the bundle
- **THEN** verification confirms the signature, that artifact digests match, and reports the toolchain versions attested — or fails naming exactly what did not match

#### Scenario: Air-gapped honesty

- **WHEN** a bundle is produced air-gapped without a key
- **THEN** it is marked unsigned in the bundle itself, and no surface presents it as attested

### Requirement: Embedded software BOM

Every evidence bundle SHALL embed a machine-readable software BOM (CycloneDX-class) of the executing environment — Anvilate version, dependency lockfile digest, bundled solver and database versions — so the computing environment is auditable with standard SBOM tooling.

#### Scenario: Auditor inventories the toolchain

- **WHEN** an auditor opens the bundle's BOM with standard SBOM tooling
- **THEN** they can enumerate every component and version that produced the results

### Requirement: AI-involvement disclosure

The evidence bundle SHALL record, machine-readably, whether and where an LLM participated in producing the spec (compilation from prose, critic edits), which model and backend, and the human confirmation events; a bundle for a spec drafted with LLM involvement MUST NOT omit the disclosure.

#### Scenario: Disclosure present and specific

- **WHEN** a spec was compiled from prose by a local model and confirmed by the user
- **THEN** the bundle records the model identity, the compilation events, and the confirmation, distinguishing LLM-drafted values from user-stated and database-resolved ones

#### Scenario: No AI, says so

- **WHEN** a spec was authored entirely by hand
- **THEN** the disclosure states that no LLM participated

