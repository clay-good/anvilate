# responsible-charge-review Specification

## Purpose
What a licensed engineer sees before deciding whether to seal. The dossier reorders a scorecard by what deserves scrutiny rather than by declaration order, attributes each decision to the deterministic engine or to a person, and records a review as an explicit, scoped action against a specific artifact — so a review that the artifact moved under counts for less than no review at all. Nothing here is professional certification, and the capability says so in its own output.

## Requirements
### Requirement: The reviewer dossier

The system SHALL assemble, for any validated part, a reviewer dossier containing: the
inputs and where each came from, every assumption the pipeline made and whether a person
or a model supplied it, every check with its verdict, margin, citation with edition, and
screening label, every check that could not be evaluated and why, the governing checks
and constraints, the iteration history including what changed and why, and the residual
limitations of the analysis. The dossier SHALL be reviewable offline and exportable with
the evidence bundle.

#### Scenario: Everything needed to scrutinize, in one place

- **WHEN** a reviewer opens the dossier for a validated part
- **THEN** inputs, assumptions with their origin, verdicts with citations, unevaluated
  checks with reasons, governing checks, iteration history, and stated limitations are
  all present without leaving the dossier

#### Scenario: Unevaluated work is prominent

- **WHEN** checks report "not evaluated"
- **THEN** they appear in the dossier as items requiring the reviewer's attention, never
  folded into a summary that reads as complete

### Requirement: Attention is ordered by what deserves scrutiny

The dossier SHALL order or highlight its contents by review priority — at minimum:
failing checks, unevaluated checks, checks passing on thin margins, results resting on
model-supplied assumptions, results resting on user-supplied allowables, and results
carrying uncertainty warnings — so a reviewer can find what matters without reading
everything linearly. The prioritization rule SHALL be deterministic and documented, not
model-generated.

#### Scenario: Thin margins surface

- **WHEN** one check passes at a 2% margin among many comfortable passes
- **THEN** it is surfaced in the priority ordering rather than buried

#### Scenario: Model-supplied assumptions surface

- **WHEN** an assumption came from the intent compiler rather than the user
- **THEN** results depending on it are flagged for review attention

### Requirement: AI involvement is attributed per decision

The dossier SHALL state, for each recorded decision, whether it originated from the user,
from a deterministic computation, or from a model — naming the model and version where
one was involved — and SHALL provide a summary of overall AI involvement suitable for
disclosure. A decision whose origin was not recorded SHALL be shown as unattributed
rather than assumed to be human or deterministic.

#### Scenario: Per-decision origin visible

- **WHEN** the compiler inferred a load case and the pipeline computed a margin
- **THEN** the dossier attributes the inference to the named model and version, and the
  margin to deterministic computation

#### Scenario: Unknown origin is not laundered

- **WHEN** a decision's origin is unrecorded
- **THEN** it renders as unattributed

### Requirement: Review is an explicit, recorded, scoped action

A reviewer SHALL be able to record a review outcome — reviewer identity, date, the exact
artifact version reviewed identified by its content digest, the scope reviewed, the
outcome, and any conditions or exceptions noted. A review record SHALL bind to that
artifact version only: any subsequent change to the spec, toolchain versions, or results
SHALL invalidate the record, and the system SHALL show the artifact as unreviewed with
the reason. Review records MUST NOT alter any check verdict.

#### Scenario: Review binds to a version

- **WHEN** a part is reviewed and then a dimension changes
- **THEN** the prior review is shown as invalidated naming the change, and the part
  renders as unreviewed

#### Scenario: Partial review is honest

- **WHEN** a reviewer records review of the structural checks only
- **THEN** the recorded scope reflects that, and unreviewed areas are shown as such

#### Scenario: Review changes no verdict

- **WHEN** a reviewer approves a part with a failing check noted as an accepted exception
- **THEN** the check still renders as failing, with the exception recorded alongside it

### Requirement: Review status is never professional certification

The system MUST NOT present a recorded review as a professional seal, stamp,
certification, or a determination that any legal or licensure obligation has been
satisfied, and MUST NOT describe an artifact as approved for construction, fabrication,
or service on the basis of a recorded review. Every rendering of review status SHALL
retain the screening-analysis disclaimer.

#### Scenario: Language stays honest

- **WHEN** review status is rendered anywhere in the product, a report, or an evidence
  bundle
- **THEN** it is stated as a recorded review by a named person with the screening
  disclaimer intact, and no wording implies certification or fitness for construction

#### Scenario: Responsible charge stays with the engineer

- **WHEN** the dossier is presented for sign-off
- **THEN** it states that the reviewing engineer retains responsible charge and that
  Anvilate's results are screening-level evidence supporting, not replacing, their
  judgment

