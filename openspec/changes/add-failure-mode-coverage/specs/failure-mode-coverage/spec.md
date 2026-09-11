# Failure-Mode Coverage Specification (delta)

## ADDED Requirements

### Requirement: A cited catalog of failure modes, applicable by declared fact

The system SHALL maintain a versioned catalog of failure modes, each record carrying an
id, a plain-language description, the declared facts that make it applicable, the stage at
which it would otherwise be discovered, and a citation to the source establishing it as a
real mode. Applicability SHALL be resolved from declared, typed facts — element class,
material pairing, interface kind, environment, process — and MUST NOT be matched against
free text in the spec, because a catalog keyed on wording applies itself to the way a user
happened to describe a part rather than to the part.

#### Scenario: Applicability follows the declaration

- **WHEN** a spec declares a joint between two dissimilar metals in a declared humidity
  environment
- **THEN** the galvanic mode resolves as applicable from those declared facts, regardless
  of the words the user used

#### Scenario: Every mode names its source

- **WHEN** a catalog record is rendered
- **THEN** it carries the citation establishing the mode, so a reader can check that the
  mode is real rather than invented

#### Scenario: Renaming a part changes nothing

- **WHEN** a part's description is reworded without changing a declared fact
- **THEN** the applicable-mode set is identical

### Requirement: Every applicable mode resolves to screened, verification-only, or unaddressed

Each applicable mode SHALL resolve to exactly one of three states: screened, naming the
check that addresses it; verification-only, naming the test archetype that would establish
it because no analysis in the system can; or unaddressed, meaning applicable with neither.
The mapping from checks to the modes they address SHALL be declared by the checks
themselves so it is data rather than inference, and an applicable mode MUST NOT be omitted
from the report because nothing happened to cover it — that omission is the failure this
capability exists to prevent.

#### Scenario: An unaddressed mode is named on a passing part

- **WHEN** every check passes and one applicable mode has no check and no test
- **THEN** the report names that mode, its description, and its discovery stage

#### Scenario: A screened mode names its check

- **WHEN** a mode is addressed
- **THEN** the report names the check and that check's verdict, so a mode covered by a
  failing check is not counted as handled

#### Scenario: Analysis cannot reach it, and the report says which test can

- **WHEN** a mode is path-dependent or statistical beyond what closed-form screening
  reaches
- **THEN** it resolves as verification-only naming the test archetype, and a test item is
  available to the verification plan

### Requirement: Coverage is a count over a named population, never a bare percentage

Coverage SHALL be reported as the number of modes in each state together with the total
applicable population, and the unaddressed set SHALL always be enumerated by name. A
percentage MAY accompany those numbers but MUST NOT appear without them, because a
coverage figure with no denominator and no names reassures a reader without informing
them, and a shrinking catalog would otherwise raise the percentage.

#### Scenario: The denominator travels with the figure

- **WHEN** a coverage summary is rendered
- **THEN** it states the screened, verification-only, and unaddressed counts and the total,
  and lists the unaddressed modes

#### Scenario: An empty catalog cannot report full coverage

- **WHEN** no catalog entries are applicable to a part class because none exist for it
- **THEN** the report states that the catalog holds no entries for that class, rather than
  reporting complete coverage over an empty population

### Requirement: Each mode states the stage at which it would otherwise be found

Every catalog record SHALL declare the stage at which the mode would be discovered if it
is not screened — design, assembly, qualification, or field — and the report SHALL group
unaddressed modes by that stage, so the engineer can see which gaps are cheap to leave and
which become expensive. The stage SHALL be described as a discovery stage and MUST NOT be
rendered, sorted, or referred to as a ranking of severity, risk, or priority, which it is
not: a mode found in the field is not necessarily worse than one found at assembly, only
later and more costly.

#### Scenario: Expensive gaps are visible as such

- **WHEN** two modes are unaddressed, one normally found at assembly and one in the field
- **THEN** the report groups them by stage and states what the stage means

#### Scenario: Stage is not severity

- **WHEN** the report is rendered
- **THEN** it states that discovery stage describes when a mode surfaces and its cost of
  discovery, not how serious it is

### Requirement: The catalog is a floor that rises, and says so

The system SHALL state, wherever coverage is reported, that the catalog is not exhaustive
and that an absence of applicable modes is not evidence of their absence in reality. An
escaped defect — a mode that reached hardware and was not in the catalog — SHALL add a
catalog entry as well as a regression case, so the floor rises from experience rather than
staying where it was first written.

#### Scenario: The claim is bounded

- **WHEN** a failure-mode report is rendered or exported
- **THEN** it states that the catalog is a floor and that full coverage of the catalog is
  not full coverage of reality

#### Scenario: Experience raises the floor

- **WHEN** an escaped defect is post-mortemed
- **THEN** a catalog entry is added alongside the regression test, and the coverage
  denominator for affected parts moves accordingly
