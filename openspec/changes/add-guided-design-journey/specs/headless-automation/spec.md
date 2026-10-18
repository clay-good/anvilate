# Headless Automation Specification (delta)

## ADDED Requirements

### Requirement: Every workflow result names the next step

Every workflow tool result SHALL carry `next` (validation, build, combination, product
build, FEA, study and export results alike): an ordered list of typed steps, each naming the tool, the
subject or argument to pass, and a one-line reason. The list SHALL be derived
deterministically from the result alone, in this order of precedence: a refusal's
remedies; failed checks that carry an inverse repair; tiers the document demands that did
not run; placeholders and unsourced values that hold back a verdict; and, when nothing
holds the result back, the export of the review package. Identical results SHALL produce
identical `next` lists. A step SHALL never name a tool the catalog does not publish, and
the list SHALL never be empty while the journey state is short of `review_ready`.

#### Scenario: A failing check with an inverse

- **WHEN** a bracket's only failure is a bending check whose inverse solves a thickness of
  7.4 mm
- **THEN** the first step in `next` is the validation tool with the spec amended to the
  solved thickness, and its reason names the check and the solved value

#### Scenario: A passing card with an unrun tier

- **WHEN** every T1 check passes and the spec demands T3 FEA, which did not run
- **THEN** `next` names the FEA tool for that spec before any export, and the result's
  verdict is not `passed`

#### Scenario: The list is held against the catalog

- **WHEN** a tool is renamed or removed from the catalog
- **THEN** a test that walks every `next` rule fails until no rule names the old tool

### Requirement: Results state the journey stage and what holds it back

A part, combination or product result SHALL state the furthest journey stage it has
reached (`described`, `screened`, `simulated`, `optimized`, `review_ready`) and, for each
later stage, the gaps that hold it back by name. `simulated` SHALL be reached only when
every FEA check the document demands has a converged verdict; `optimized` only when a
declared study has completed or been declared unnecessary with a reason; `review_ready`
only when every claim the document makes has a verdict or a declared reason for having
none, and the review package has been written for this exact content digest. A stage
that does not apply to the document (no FEA demanded, no study declared) SHALL be stated
as not applicable, never as reached.

#### Scenario: Stopping early is visible

- **WHEN** an agent ends a session on a product whose T1 card passes and whose housing
  FEA has not run
- **THEN** the last result states the stage `screened` and names the housing FEA as the
  gap to `simulated`

#### Scenario: A changed design loses its stage

- **WHEN** a dimension changes after the review package was written
- **THEN** the stage falls back to the furthest stage the new content has reached, naming
  the change

### Requirement: The review package is the finish line

The export tool SHALL offer a `review_package` format that writes, for one content
digest, the evidence bundle, the reviewer dossier, the release-package files the
document supports, and any study record, into the server's output folder, and returns
their paths. The package SHALL be refused while the result is short of `review_ready`
unless a draft is asked for, and a draft package SHALL be marked draft in every file it
writes. Writing the package SHALL record no review, approval or sign-off.

#### Scenario: A draft package says so

- **WHEN** the agent exports a draft review package for a product whose FEA did not run
- **THEN** every file is marked draft and the dossier's first page lists the FEA as not
  evaluated

#### Scenario: The package is not an approval

- **WHEN** a review-ready package is written
- **THEN** the product still renders as unreviewed until a named reviewer records a review

### Requirement: The design journey is measured end to end

The agent-driving corpus SHALL include a *design a product* journey: from a plain-English
product request to a review-ready package, through screening, inverse repair, FEA where
demanded, and a budgeted study. The journey SHALL be walked call by call in an offline
test and measured with real agents on each target client, recording completion, call
count, tool-call errors and wall-clock; a release SHALL NOT ship if the journey completes
on the previous release's measurement and not on this one.

#### Scenario: The journey regresses

- **WHEN** a release candidate's measured run completes the product journey on one
  client where the previous release completed it on both
- **THEN** the release gate fails, naming the client and the step where the run stopped
