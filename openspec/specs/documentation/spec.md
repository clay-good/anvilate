# Documentation Specification

## Purpose

Documentation is a product surface, not an afterthought: every guide, reference page, error message, and in-app explanation is written for a working engineer, in plain language, kept correct by CI, and available offline. If a user has to ask "what does this mean?", the documentation has a bug.

## Requirements

### Requirement: Task-first documentation set

Documentation SHALL be organized around user tasks, not internal architecture: a quickstart (install → first validated part), per-persona guides (mechanical, structural, industrial), how-to pages for each export target, and reference material last; the quickstart MUST be completable by a new user in under 10 minutes of reading.

#### Scenario: Quickstart is the front door

- **WHEN** a new user opens the documentation site or the bundled docs
- **THEN** the first page is the quickstart, and following it verbatim on a supported platform produces an exported validated sample part

#### Scenario: Persona guide entry points

- **WHEN** a structural engineer opens the docs
- **THEN** a guide exists that walks their golden path (e.g., a code-checked base plate to DXF) without requiring them to read mechanical-engineering examples first

### Requirement: Plain-language standard

All user-facing documentation SHALL use plain language: every domain term is defined on first use or linked to a single glossary, internal codenames and architecture jargon MUST NOT appear in user documentation, and sentences state what the user should do before explaining why.

#### Scenario: Jargon is always resolvable

- **WHEN** documentation uses a technical term such as "mesh convergence" or "semantic PMI"
- **THEN** the term links to a glossary entry that explains it in two or three plain sentences with a concrete example

#### Scenario: No internal vocabulary leaks

- **WHEN** documentation is reviewed before release
- **THEN** internal subsystem names (e.g., "intent compiler", "T2 tier") appear only in contributor docs, while user docs say what the user sees ("the spec card", "manufacturing checks")

### Requirement: Every check has an explanation page

Every validation check ID SHALL have a documentation page stating, in plain language: what the check verifies, why it matters physically, common causes of failure, and concrete fixes; the scorecard and evidence bundle MUST link each check result to its page.

#### Scenario: Failing check links to its fix

- **WHEN** a wall-thickness check fails in the report pane
- **THEN** the failure entry links to the page for that check, which explains the manufacturing reason for the minimum and lists typical remedies (thicken the wall, change process, split the part)

#### Scenario: No orphan checks

- **WHEN** a new check is added to the validation engine
- **THEN** CI fails if no documentation page exists for its check ID

### Requirement: Actionable error messages

Every user-facing error SHALL state what happened, the likely cause, and the next action in plain language; raw tracebacks and solver logs MUST be collapsed behind a details control, never the primary message.

#### Scenario: Solver failure in plain words

- **WHEN** the FEA solver fails on a pathological mesh
- **THEN** the user sees a message such as "The stress analysis could not run because meshing failed near <feature>. Try increasing the minimum feature size, or export without validation." with the solver log available under details

### Requirement: Documentation examples are executed in CI

Every copy-pasteable command, spec file, and code example in the documentation SHALL be executed in CI against the release candidate, and a failing example MUST block the release.

#### Scenario: Rotten example blocks release

- **WHEN** a CLI flag is renamed and a quickstart command no longer runs
- **THEN** the docs CI job fails and the release is blocked until the example or the flag is fixed

### Requirement: Single-sourced, offline-available help

In-app help content SHALL render from the same source files as the published documentation, and the full documentation set SHALL be bundled with the install so every page is available offline and in air-gapped mode.

#### Scenario: Air-gapped user reads the docs

- **WHEN** a user on an air-gapped machine opens help for a failing check
- **THEN** the same explanation page renders locally with zero network calls

### Requirement: Versioned documentation

Documentation SHALL be versioned with each release, and links from a running instance MUST resolve to the documentation version matching that instance.

#### Scenario: Old release, matching docs

- **WHEN** a user on release 1.2 opens help
- **THEN** they see 1.2 documentation, not documentation describing features from a later release
