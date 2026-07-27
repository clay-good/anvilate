# Standards & Materials Data Specification (delta)

## ADDED Requirements

### Requirement: Design-allowables basis is first-class

The materials schema SHALL distinguish the statistical basis of every strength property — typical, A-basis, B-basis, or specification minimum — and a bundled design-allowables pack seeded from public-domain sources (MIL-HDBK-5J class) SHALL provide basis-tagged allowables with table-level citations and an explicit superseded-status note where a newer paywalled edition exists; checks consuming a property SHALL be able to state the basis in their results.

#### Scenario: Basis visible in the verdict

- **WHEN** a strength check runs against a B-basis allowable from the design-allowables pack
- **THEN** the scorecard entry states the basis and the table citation, distinguishable from a typical-value property

#### Scenario: Superseded status disclosed

- **WHEN** a value from a superseded public-domain edition is used
- **THEN** the provenance record and report carry the note that a newer edition exists and where certification-grade work should source values

### Requirement: Fatigue data ingestion

The database SHALL support fatigue-data records (S-N curve parameters, test conditions, specimen metadata) from two ingestion paths: registration-gated open databases via the existing fetch-on-first-use flow (NIMS MatNavi class, with the registration step documented), and redistributable research datasets bundled with DOI-level provenance and license records; fatigue checks consuming ingested data SHALL cite the dataset and distinguish test-data-backed curves from estimated parameters.

#### Scenario: Real S-N data replaces an estimate

- **WHEN** a fatigue screen runs on a material whose ingested dataset provides a test-backed S-N curve
- **THEN** the check uses and cites the dataset curve, and the "estimated per FKM method" label is absent because the value is test-backed

#### Scenario: Gated database fetched with consent

- **WHEN** a spec first needs a fatigue record from a registration-gated open database
- **THEN** the user is walked through the documented registration/fetch step once, the data is cached locally with source and license recorded, and later lookups work offline

### Requirement: Named structural sections resolve via importers

Named structural sections SHALL resolve through per-region importers: license-restricted compilations (AISC shapes class) via the existing fetch-on-first-use flow with checksum and provenance, and openly licensed profile data (EN 10365-dimension sources) bundled with citations; after import, a named section reference (e.g., "W12x26", "IPE 200") SHALL resolve offline to dimensions and computed properties feeding the existing structural checks.

#### Scenario: Named shape to cited check

- **WHEN** a spec references "W12x26" after the one-time AISC data fetch
- **THEN** the section resolves offline with fetch provenance recorded and its properties feed the existing cited beam/column screens

#### Scenario: European profile out of the box

- **WHEN** a spec references "IPE 200" with no prior fetch
- **THEN** the bundled open profile data resolves it with its source citation, with zero network calls

### Requirement: Bundled tables published as a standalone dataset

The bundled dimension and materials tables SHALL be published as a standalone, versioned, citation-tagged open dataset with a documented schema and contribution process, decoupled from Anvilate releases; Anvilate SHALL consume the dataset by pinned version, and third-party consumers SHALL be able to use it without Anvilate.

#### Scenario: Dataset consumed independently

- **WHEN** a third-party tool loads the published dataset
- **THEN** it can resolve records, citations, and licenses from the dataset alone, without importing Anvilate

#### Scenario: Version pinning in provenance

- **WHEN** an Anvilate build resolves any record
- **THEN** the evidence records the dataset version pin, and a dataset upgrade is a visible provenance change
