# Discipline Packs Specification (delta)

## MODIFIED Requirements

### Requirement: Discipline pack contract

A discipline pack — equivalently, a **physical-domain module** — SHALL declare a typed
manifest and bundle the artifacts that manifest promises. The manifest SHALL carry: a
stable module id and the check-id namespace reserved to it; a semantic version; a default
unit system; every standard it implements with its edition; the material property sets its
checks require; the pipeline tiers it participates in; and the module ids it depends on.
The bundle SHALL carry: pattern archetypes meeting the pattern-library contribution
contract, standards-database records with provenance, check sets returning standard
scorecard records, process/DFM profiles, sample specs, user documentation, and golden-file
tests. Modules MUST plug into the existing tiers and gates and MUST NOT bypass validation,
export gating, or sandboxing.

#### Scenario: Pack parts flow through the same gauntlet

- **WHEN** a part from an enabled discipline pack is built
- **THEN** it runs the same T0–T3 tiers, produces a standard scorecard, and is export-gated exactly like a core mechanical part

#### Scenario: Incomplete pack rejected

- **WHEN** a pack is submitted missing check citations, golden-file tests, or documentation
- **THEN** CI rejects it with the missing contract items enumerated

#### Scenario: Manifest is complete or the module does not load

- **WHEN** a module declares a standard with no edition, a check outside its reserved
  namespace, or a dependency on a module that is not present
- **THEN** loading fails naming the offending manifest field, rather than loading a module
  whose promises cannot be checked

#### Scenario: Declared standards resolve both directions

- **WHEN** CI validates a module manifest
- **THEN** every standard the manifest declares is used by at least one of the module's
  checks, and every standard the module's checks cite is declared in the manifest

## ADDED Requirements

### Requirement: Modules compose existing screens rather than duplicating them

A module SHALL reuse an existing screen wherever one implements the limit state it needs,
composing it under the module's own design factors and citations; a module MUST NOT ship a
second implementation of a limit state another module or the core analysis library already
provides. Where two loaded modules would report on the same limit state for the same
declaration, the system SHALL report one result naming the governing module and its
factors — never two results the reader must reconcile.

#### Scenario: Shared limit state is evaluated once

- **WHEN** two enabled modules both bear on a pin-connected plate
- **THEN** the scorecard carries one set of lug limit-state entries, naming which module's
  design factors governed, and not two conflicting sets

#### Scenario: Duplicate implementation rejected in CI

- **WHEN** a submitted module implements a limit state the analysis library already
  provides
- **THEN** CI rejects it naming the existing symbol it should have composed

### Requirement: Modules declare what they can screen and refuse the rest by name

Every module SHALL declare the set of spec declarations its checks can screen. When an
enabled module is the owner of a declaration it cannot screen, the scorecard SHALL carry a
"not evaluated" entry naming the module, the declaration, and what screening it would take
— a module MUST NOT leave a declaration in its own domain silently unanswered.

#### Scenario: In-domain declaration outside coverage is named

- **WHEN** a spec declares a feature that belongs to an enabled module's domain but falls
  outside that module's declared coverage
- **THEN** the scorecard names the module and the declaration in a not-evaluated entry,
  and the card does not pass

#### Scenario: Coverage claim is tested

- **WHEN** CI validates a module
- **THEN** every declaration in the module's declared coverage set is exercised by at
  least one test, so the claim cannot be wider than the implementation

### Requirement: New domains are specified in their own capability

A new physical domain SHALL be specified as its own capability spec that references this
module contract, rather than by appending domain-specific requirements to this shared
spec. This spec governs what every module owes; a domain spec governs what that domain's
screens compute and cite.

#### Scenario: A new domain does not edit the shared contract

- **WHEN** a tenth domain is proposed
- **THEN** its change adds a capability spec for that domain and, at most, adds
  general-purpose requirements here — it does not enumerate the new domain's screens in
  this spec

### Requirement: Module versioning and deprecation are visible

A module's version SHALL be recorded in every scorecard and evidence bundle it
contributes to, so a result can be traced to the module revision that produced it. A
module or a check within one MAY be deprecated; a deprecated check SHALL continue to
compute while rendering its deprecation and the replacement's identity, and SHALL NOT be
removed without a version increment that says so.

#### Scenario: Result traces to a module version

- **WHEN** an evidence bundle is produced from a build that used two enabled modules
- **THEN** the bundle records each module's id and version

#### Scenario: Deprecation is announced, not silent

- **WHEN** a deprecated check runs
- **THEN** its scorecard entry states that it is deprecated and names its replacement

### Requirement: Every published check is exercised

CI SHALL assert, per module, that every check the module publishes is reached by at least
one test and appears in at least one runnable example. The gate SHALL be expressed as a
fraction of the module's published checks together with an assertion on the population
size, so that a module which publishes nothing, or which shrinks its published set, fails
rather than passes.

#### Scenario: An unexercised check fails CI

- **WHEN** a module publishes a check no test calls
- **THEN** CI fails naming the check

#### Scenario: An empty module cannot satisfy the floor

- **WHEN** the set of a module's published checks is empty or smaller than its manifest
  declares
- **THEN** the gate fails on the population-size assertion rather than reporting a
  vacuous hundred percent

### Requirement: Third-party modules load only on opt-in and are marked

Modules from outside the repository SHALL load only when the user explicitly enables them
by path or distribution name, SHALL execute under the existing sandbox constraints, and
SHALL be marked unverified-origin. Every scorecard entry and evidence bundle a
third-party module contributes to SHALL carry that marking, and export gating SHALL treat
an unverified-origin result as evidence the reader must weigh, never as equivalent to an
in-tree check.

#### Scenario: Out-of-tree module is not silently trusted

- **WHEN** a user enables a third-party module and builds a part
- **THEN** the module's contributions are marked unverified-origin in the scorecard and
  the evidence bundle records the module's origin and version

#### Scenario: No implicit discovery

- **WHEN** a third-party module is installed but not explicitly enabled
- **THEN** it contributes no vocabulary, patterns, samples, or checks

### Requirement: Limit states are identified, not inferred from names

A module SHALL identify each limit state it evaluates by an id drawn from a shared
registry of limit-state concepts, and the composition and duplicate-detection rules SHALL
operate on those ids. Detection MUST NOT be performed by matching function names,
docstrings, or citation text, because two implementations of one limit state routinely
carry different names and one name routinely covers two limit states. A module evaluating
a limit state absent from the registry SHALL add it to the registry in the same change.

#### Scenario: Differently named duplicates are still caught

- **WHEN** a submitted module implements a limit state the library already provides under
  a different function name
- **THEN** the duplicate is detected by the shared id and CI fails naming both

#### Scenario: An unregistered limit state cannot slip through

- **WHEN** a module evaluates a limit state with no registry id
- **THEN** CI fails requiring the registry entry, so the composition rule has something to
  key on

#### Scenario: One name covering two limit states does not collide

- **WHEN** two checks share a name but carry distinct limit-state ids
- **THEN** they are treated as distinct and neither is reported as a duplicate

### Requirement: Namespace and id collisions are refused at load

Loading SHALL fail when two enabled modules reserve overlapping check-id namespaces, when
a module publishes a check id outside its reserved namespace, or when two modules declare
the same module id at different versions. The failure SHALL name both modules and the
colliding identifier; the system MUST NOT resolve a collision by precedence, because a
silently shadowed check is a check that stopped running.

#### Scenario: Overlapping namespaces do not load

- **WHEN** two enabled modules reserve the same namespace prefix
- **THEN** loading fails naming both modules and the prefix

#### Scenario: No last-wins resolution

- **WHEN** two modules publish the same check id
- **THEN** loading fails rather than keeping one and discarding the other

### Requirement: The enabled module set is part of the reproducibility contract

The enabled module set SHALL be captured in the evidence bundle and required for
reproduction — every module id and version, including disabled-but-installed modules
recorded as disabled — because a build's result depends on which modules were enabled. Reproducing a build with a
different enabled set SHALL be reported as a different configuration rather than a
mismatch of results, and a bundle that does not record its enabled set SHALL be treated as
irreproducible.

#### Scenario: Reproduction states the configuration it needs

- **WHEN** a bundle is reproduced on another machine
- **THEN** the reproduction checks the enabled module set first and reports a
  configuration difference by name before comparing any result

#### Scenario: A module enabled later explains a changed verdict

- **WHEN** enabling an additional module changes a scorecard
- **THEN** the difference is attributable to the enabled set recorded in each bundle

### Requirement: A module's unit default never overrides a declared unit system

A module's declared default unit system SHALL apply only when a spec states no unit system
of its own; a spec's declared system always wins. Where two enabled modules declare
different defaults and the spec declares none, the system SHALL ask rather than choosing,
because silently rendering a report in the wrong system is the failure the units
capability exists to prevent.

#### Scenario: The spec's declaration wins

- **WHEN** a spec declares SI and an enabled module defaults to US customary
- **THEN** every surface renders in SI

#### Scenario: Conflicting defaults ask rather than pick

- **WHEN** a spec declares no unit system and two enabled modules default differently
- **THEN** the compiler asks one question naming both modules, rather than defaulting
