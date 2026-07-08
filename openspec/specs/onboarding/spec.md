# Onboarding & Installation Specification

## Purpose

Onboarding is the path from "never heard of Anvilate" to "exported my first validated part" with no configuration, no account, and no expertise about the tool itself. Every minute and every decision on that path is a cost; this capability budgets both.

## Requirements

### Requirement: One-command install per platform

Anvilate SHALL install with a single documented command per supported channel (pip, Docker/Podman, conda-forge), and installation MUST NOT require the user to manually install, locate, or configure solvers, meshers, or the geometry kernel — bundled or auto-fetched components resolve without user action.

#### Scenario: pip install just works

- **WHEN** a user runs the documented pip install command on a supported platform and starts Anvilate
- **THEN** the workbench opens and a sample part builds and validates without any manual solver setup

#### Scenario: Container parity

- **WHEN** a user runs the official container image
- **THEN** the same golden path works with no host installation beyond the container runtime

### Requirement: Environment self-check

Anvilate SHALL provide a self-check command (`anvilate doctor`) that verifies solvers, geometry kernel, local model runtime, viewport prerequisites, and database integrity, reporting each item as pass/fail with a plain-language fix for every failure.

#### Scenario: Missing solver diagnosed

- **WHEN** the FEA solver binary is missing or the wrong version
- **THEN** `anvilate doctor` reports exactly that item as failed with the command or action that fixes it, and all other items still report their true status

### Requirement: Zero-configuration first run

First launch SHALL require no account, no login, no API key, and no configuration file; if no local model is present, Anvilate SHALL offer a recommended local model with its download size and let the user defer — sample parts and the UI MUST remain explorable before any model is installed.

#### Scenario: Explore before model download

- **WHEN** a user launches Anvilate for the first time with no model installed
- **THEN** they can open the sample gallery, build a bundled sample spec, and inspect its validation report, with model download offered but not required

#### Scenario: Model offer is informed

- **WHEN** the model download is offered
- **THEN** the offer states the model name, disk size, and that it runs fully locally, with a one-click accept or defer

### Requirement: Sample part gallery

Anvilate SHALL bundle at least 5 runnable sample specs spanning the supported personas (e.g., motor bracket, enclosure, structural base plate, lifting lug, fixture plate), each loadable and buildable in one action with zero network calls; the empty-state workbench SHALL present the gallery.

#### Scenario: First part in one click

- **WHEN** a new user clicks a gallery sample
- **THEN** the spec card, geometry, and validation report populate from the bundled spec, demonstrating the full describe → validate → export loop without the user typing anything

### Requirement: Time-to-first-part budget

The path from a completed fresh install to an exported validated sample part SHALL take under 10 minutes on the reference hardware profile, excluding model download time; this budget SHALL be measured for each release on the reference profile and a sustained regression MUST block release.

#### Scenario: Budget measured per release

- **WHEN** a release candidate is prepared
- **THEN** the measured install-to-first-export time on the reference profile is recorded, and exceeding the budget blocks the release until resolved or the budget is consciously revised

### Requirement: Optional guided first build

On the user's first own part (not a sample), Anvilate SHALL offer a dismissible walkthrough of the three panes and the spec-card confirmation; the walkthrough MUST never block input and MUST never reappear once dismissed.

#### Scenario: Walkthrough respects the user

- **WHEN** an experienced user dismisses the walkthrough and starts typing
- **THEN** no further onboarding UI interrupts them in that or any later session
