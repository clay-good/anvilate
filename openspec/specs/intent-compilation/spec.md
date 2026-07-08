# Intent Compilation Specification

## Purpose

Intent compilation turns user input — prose, pasted dimension tables, dropped files — into a valid Design Spec IR. It is the first of only two subsystems permitted to call an LLM, and its output is always schema-constrained: free text never flows past this stage.

## Requirements

### Requirement: Schema-constrained compilation

The intent compiler SHALL produce only Design Spec IR documents that pass schema validation, using structured-output enforcement (JSON-Schema / grammar-constrained decoding); free-form LLM text MUST NOT be passed to any downstream subsystem.

#### Scenario: Prose compiles to typed spec

- **WHEN** the user submits "Aluminum 6061 mounting bracket for a NEMA 23 stepper motor, bolts to a 4040 extrusion rail with M5 T-nuts, motor weighs 1.1 kg cantilevered, machine vibrates, under 150 g, CNC machined"
- **THEN** the compiler emits a Spec IR with material, two standard-component interfaces, a gravity load case, a vibration-derived quasi-static load case, a mass constraint, and a manufacturing process — all as typed fields

#### Scenario: Malformed LLM output retried, never forwarded

- **WHEN** the LLM emits output that fails Spec IR schema validation
- **THEN** the compiler retries with the validation error in context up to a bounded retry budget
- **AND** on exhaustion it reports a compilation failure to the user rather than forwarding unvalidated output

### Requirement: Retrieval, not recall, for standard dimensions

The compiler SHALL select standard components and materials by database identifier only; it MUST NOT emit numeric dimensions for standard components from model memory. Dimension data flows exclusively from the standards database.

#### Scenario: Bolt pattern from database

- **WHEN** the user mentions "NEMA 23 stepper"
- **THEN** the compiler emits `ref: "NEMA23"` and the 47.14 mm bolt-square, pilot-bore, and face dimensions are resolved downstream from the standards database

#### Scenario: Unrecognized component

- **WHEN** the user names a component with no database match (e.g., an obscure motor model)
- **THEN** the compiler asks the user for the governing dimensions or a datasheet/STEP file instead of guessing
- **AND** the resulting spec marks that interface as user-supplied with provenance

### Requirement: Bounded clarification policy

The compiler SHALL ask clarifying questions only for values that are both unstated and high-consequence (load magnitude, material, fixed interface), MUST limit clarification to at most 3 short questions per compilation with tappable defaults, and SHALL apply labeled, defensible defaults for everything else.

#### Scenario: Sensible defaults applied and shown

- **WHEN** the user's prose omits safety factor and vibration severity
- **THEN** the compiler applies documented defaults (e.g., SF 2.0; 3g quasi-static envelope)
- **AND** each default appears in the spec card as an editable assumption with rationale

#### Scenario: High-consequence ambiguity triggers a question

- **WHEN** the user requests a load-bearing part without stating the load
- **THEN** the compiler asks one short question with a tappable default rather than silently inventing a load

### Requirement: Multi-modal input acceptance

The compiler SHALL accept, in addition to prose: pasted dimension tables, STEP files of mating parts (routed to interface detection), DXF files of mounting plates, and — per the input-ingestion capability — datasheet PDFs and drawing images.

#### Scenario: Pasted dimension table

- **WHEN** the user pastes a table of hole positions and diameters
- **THEN** the compiler converts it into an explicit interface definition with each value tagged user-stated

#### Scenario: Dropped mating STEP

- **WHEN** the user drops a STEP file of a mating part
- **THEN** the file is routed to deterministic interface detection and detected candidates are offered back for confirmation, without the file contents passing through the LLM

### Requirement: LLM backend independence

The compiler SHALL run against a local model (Ollama/llama.cpp-served) or a user-supplied cloud API key interchangeably; the Spec IR contract MUST NOT change with the backend, and no cloud call SHALL occur unless the user has explicitly configured a cloud backend.

#### Scenario: Air-gapped compilation

- **WHEN** Anvilate runs in air-gapped mode with a local model
- **THEN** intent compilation completes with zero network calls

#### Scenario: Backend swap

- **WHEN** the user switches the configured model backend
- **THEN** previously saved specs remain valid and recompilation produces schema-identical spec structures

### Requirement: Spec card confirmation before build

The compiler SHALL present the compiled Design Spec to the user as a reviewable spec card — showing every interface, load case, constraint, and assumption — before the first geometry build, unless the user has enabled auto-build.

#### Scenario: User confirms spec

- **WHEN** compilation completes
- **THEN** the spec card is rendered with envelope, interfaces, load cases, material, constraints, and defaults-as-chips
- **AND** the build starts only on user confirmation or configured auto-build
