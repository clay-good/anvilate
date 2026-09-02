# calculation-report Specification

## Purpose
The document a checker actually reviews. A scorecard says a design passed; a calculation report shows the formula, the values substituted into it, the result and the clause — carried by the check itself, so the rendering cannot drift from what was computed. It renders deterministically, offline and in pure Python to one self-contained HTML file, and answers in the project's unit system, because a substituted line a reviewer cannot evaluate by hand is not a calculation they can check.
## Requirements
### Requirement: Worked derivation for every check

Every analytical check SHALL be renderable as a worked derivation showing, in order: the governing symbolic formula, the formula with the check's actual values substituted (each with its unit), and the result with its unit and pass/fail margin; the derivation SHALL carry the check's citation (handbook or standard clause) and a glossary line for every symbol used.

#### Scenario: Bending check shows its work

- **WHEN** a cantilever bending check is rendered as a derivation
- **THEN** the report shows the symbolic stress formula, the same formula with the actual force, length, and section values substituted with units, the resulting stress against the allowable with the safety factor, and the source citation

#### Scenario: Symbols are never bare

- **WHEN** any derivation renders a symbol
- **THEN** the report's glossary defines that symbol in plain language with its unit, so a reviewer unfamiliar with the source text can follow the calculation

### Requirement: Derivation metadata is part of the check contract

Analysis functions SHALL declare derivation metadata — symbolic form, symbol glossary, and citation — as a typed, versioned artifact alongside their implementation; a check lacking derivation metadata SHALL render as a tabular inputs/outputs fallback clearly labeled as such, and CI SHALL report the coverage ratio and fail when a newly added check ships without metadata.

A check that ships without derivation metadata SHALL be registered under one of **three** distinct kinds, and the registry SHALL NOT collapse them: a **lookup**, which has no formula to render and is complete as it stands; a **numeric result**, whose value comes from solving an equation rather than evaluating an expression, so there is no substitutable line to render and the fallback table is its correct rendering; and a **debt**, which is a closed form whose derivation has not been written. Filing a debt as either of the others converts an unfinished piece of work into a decision, which is a worse silence than the one the registry replaces.

The two **complete** kinds SHALL be declared where the check is and travel with the entry, not in a file addressed by citation: a clause cited by more than one check cannot be answered once, and a registry that answers it once is wrong for every check but the first. A check SHALL NOT be able to declare itself a **debt**: debt is the absence of any declaration, recorded per clause in the ratchet's own list, and a check that could file its own debt would retire it by describing it.

A check SHALL be counted as having answered when it carries a derivation or declares one of the two complete kinds, and a clause SHALL clear the list when every entry citing it has answered.

The debt list SHALL be downward-only: a check may leave it by acquiring a derivation, and SHALL NOT leave it by being reclassified unless the stated reason changes accordingly. A check carrying a computed safety factor SHALL NOT be able to declare that it has no formula, in any kind: a safety factor is a quotient and a quotient is a formula, so the relabelling is refused on the data rather than on the wording.

#### Scenario: New check without metadata is caught

- **WHEN** a new analysis check is merged without derivation metadata
- **THEN** CI fails naming the check, unless the check is explicitly registered as tabular-only with a stated reason

#### Scenario: Fallback is honest

- **WHEN** a tabular-only check appears in a calculation report
- **THEN** its section shows inputs, outputs, margin, and citation in a table labeled "derivation not rendered," never a fabricated formula

#### Scenario: A debt cannot be retired by relabelling

- **WHEN** a check carrying a computed safety factor declares that it has no formula
- **THEN** the entry is refused at construction, and on a copy, because a formula does not become a table by being filed as one

#### Scenario: A declaration with no reason is refused

- **WHEN** a check declares that it has no formula and states no reason
- **THEN** the declaration is refused, because a reason that says nothing is the silence the declaration exists to replace

#### Scenario: One clause, two checks, one of them worked

- **WHEN** a clause is cited by a check that renders a worked calculation and by another check that has nothing to compute
- **THEN** the coverage report counts the first as worked and the second as answered, and the clause requires no entry in a side file

### Requirement: Submittal-shaped document

The calculation report SHALL assemble check derivations into a paginated document with: a project/part header block, the code and standard editions relied upon, the assumptions and defaults in force (with origin tags), the load and input summary, per-check derivation sections grouped by discipline, a margin summary table identifying the governing check, and the screening-analysis disclaimer; the document SHALL render as HTML and PDF.

#### Scenario: Reviewer follows the basis of design

- **WHEN** an independent engineer receives only the calculation report
- **THEN** they can identify the code editions, assumptions, inputs, each check's derivation and margin, and which check governs, without asking for clarification

#### Scenario: Disclaimer is non-dismissable

- **WHEN** any calculation report is rendered
- **THEN** it carries the screening-analysis disclaimer and the statement that engineering sign-off remains with a qualified engineer

### Requirement: Machine-readable calc record

Every calculation report SHALL be accompanied by a machine-readable calc record — a stable, versioned JSON schema carrying inputs, symbolic forms, substituted values, results, margins, citations, and provenance for every rendered check — sufficient for external tooling to re-verify every number without parsing the rendered document.

#### Scenario: Firm QA script re-checks the numbers

- **WHEN** an external script loads the calc record and recomputes a check from its recorded inputs and formula reference
- **THEN** the recomputed value matches the recorded result exactly

#### Scenario: Schema is versioned

- **WHEN** the calc-record schema changes
- **THEN** the record declares its schema version and older records remain loadable per the documented migration policy

### Requirement: Deterministic, offline, pure-Python rendering

Report rendering SHALL complete offline with zero network calls, require no external TeX or browser toolchain, and be deterministic: the same scorecard and toolchain versions SHALL produce byte-identical HTML and semantically identical PDF across rebuilds.

#### Scenario: Air-gapped submittal

- **WHEN** a user on an air-gapped machine renders a calculation report to PDF
- **THEN** the render completes with zero network calls and no system TeX installation

#### Scenario: Rebuild produces no diff

- **WHEN** the same build is rendered twice
- **THEN** the HTML output is byte-identical, so report diffs reflect only engineering changes

### Requirement: Unit-system fidelity in derivations

Derivations SHALL render every value in the project's declared unit system at the code-conventional precision defined by the units capability, while the calc record carries full-precision canonical values; a substituted value MUST never appear without its unit.

#### Scenario: US project derivation

- **WHEN** a `units: US` project renders a bearing-stress derivation
- **THEN** substituted values appear in kip and inch units and the result in ksi at conventional precision, with full-precision values in the calc record

