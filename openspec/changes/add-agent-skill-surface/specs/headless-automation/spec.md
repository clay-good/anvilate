# Headless Automation Specification (delta)

## ADDED Requirements

### Requirement: First-party agent skill teaching correct use

Anvilate SHALL ship a versioned first-party agent skill in an open, vendor-neutral
capability-packaging convention, together with a repository-convention instruction file,
covering at minimum: compiling prose to a spec and confirming it; retrieving standard
dimensions from the bundled databases rather than recalling them; running the gauntlet
and reading the scorecard before reporting an outcome; interpreting "not evaluated" as
not passing; the repair loop's inverse-first order; and the export gate and screening
disclaimer. The skill SHALL be versioned with the release, state the tool-surface version
it targets, and be installable and usable offline.

#### Scenario: Skill ships and is offline-usable

- **WHEN** Anvilate is installed with no network access
- **THEN** the agent skill and repository-convention file are present, versioned, and
  usable

#### Scenario: Doctrine is conveyed, not just syntax

- **WHEN** an agent follows the skill to validate a part
- **THEN** the workflow it follows retrieves standard dimensions, reads the scorecard
  before reporting, and treats "not evaluated" as not passing

### Requirement: The skill grants nothing and bypasses nothing

The skill SHALL be documentation only. Loading it MUST NOT enable any capability,
loosen any validation, sandboxing, or export gate, or change any result; identical
requests SHALL produce identical outcomes whether or not the skill was loaded. Skill
content MUST NOT instruct an agent to bypass a gate, override an unvalidated-export
warning without user consent, or present screening results as certified analysis.

#### Scenario: Identical behavior either way

- **WHEN** the same sequence of tool calls runs with and without the skill loaded
- **THEN** the results, gates, and watermarks are identical

#### Scenario: No bypass guidance

- **WHEN** the skill text is reviewed in CI against the prohibited-guidance checks
- **THEN** any instruction that would bypass a gate or overstate a verdict fails the
  build

### Requirement: Skill content is verified against the real tool surface

Skill and convention-file content SHALL be checked in CI against the published tool
schemas and, where it contains runnable examples, executed under the existing
documentation-examples requirement. A skill referencing a tool, argument, or workflow
that no longer exists SHALL fail the build rather than ship stale.

#### Scenario: Drift breaks the build

- **WHEN** a tool argument is renamed and the skill still references the old name
- **THEN** CI fails naming the skill file and the stale reference

#### Scenario: Examples actually run

- **WHEN** the skill contains a worked example
- **THEN** it executes in CI and its output matches what the skill claims
