# Onboarding Specification (delta)

## ADDED Requirements

### Requirement: The first product, not only the first part

The bundled examples SHALL include at least one worked product that a single request to
the agent takes through the whole design journey with zero network calls: screened,
repaired where an inverse applies, simulated where a solver is installed, improved by a
bundled study, and exported as a review package. Where an optional capability is
missing, the journey SHALL still complete to a draft package, with each skipped stage
marked not evaluated and naming the command that adds the capability.

#### Scenario: The reducer on a bare install

- **WHEN** a new user with no FEA solver installed asks their agent to take the bundled
  gear reducer through to a review package
- **THEN** the agent produces a draft package in which every T1 check and drive-train
  check has a verdict, the housing FEA is not evaluated, and the dossier names the one
  command that installs the solver on this platform

### Requirement: Optional capabilities are named, never failed

`anvilate doctor` SHALL report every optional capability (FEA solver, mesher, PDF reader,
DXF writer, and any later extra) as ready, or as *optional, not installed* with the one
command that installs it on the detected platform and channel. A missing optional
capability SHALL NOT make `doctor` exit non-zero; only a broken required capability or
a broken installed optional one (wrong version, failing self-test) SHALL. Every tool that
needs an optional capability SHALL return the same remedy text `doctor` prints.

#### Scenario: No solver on a pip install

- **WHEN** `anvilate doctor` runs on a pip install with no CalculiX binary present
- **THEN** it exits 0, and lists the FEA solver as optional, not installed, with the
  install command for this platform

#### Scenario: A solver at the wrong version

- **WHEN** a CalculiX binary is found whose version is outside the pinned range
- **THEN** `doctor` exits non-zero naming the found and the supported versions
