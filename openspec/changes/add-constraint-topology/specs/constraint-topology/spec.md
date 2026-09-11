# Constraint Topology Specification (delta)

## ADDED Requirements

### Requirement: Constraints are declared and the six freedoms are tallied

A body's constraints SHALL be declared as typed data naming the feature each acts at, the
degrees of freedom it removes, and its kind, and the system SHALL report a per-degree-of-
freedom tally in a declared reference frame. Each of the six freedoms SHALL be reported as
under-constrained, exactly constrained, or over-constrained; the total SHALL be shown so a
reader can check the arithmetic, and the reference frame SHALL be stated because the tally
is meaningless without it.

#### Scenario: Exact constraint is a positive result

- **WHEN** a ball-vee-flat coupling is declared
- **THEN** the report states that all six freedoms are exactly constrained and shows the
  count each interface contributed

#### Scenario: Tally names its frame

- **WHEN** a constraint tally is rendered
- **THEN** it names the reference frame the six freedoms are expressed in

#### Scenario: Undeclared constraints are not inferred

- **WHEN** a body's constraints are not declared
- **THEN** the screen reports "not evaluated" naming the body, rather than inferring
  constraints from geometry

### Requirement: An under-constrained freedom is named physically

An under-constrained result SHALL name the freedom in physical terms — the axis or the
rotation left free, expressed against a named feature — rather than reporting a count or
an index. A residual rigid-body freedom is frequently intentional, so the result SHALL
distinguish one declared as intentional, with its purpose recorded, from one nobody
declared.

#### Scenario: The free motion is described, not numbered

- **WHEN** a mount leaves rotation about a bore axis unconstrained
- **THEN** the result says the body is free to rotate about that named bore axis

#### Scenario: An intended freedom is not noise

- **WHEN** a freedom is declared intentional, such as an adjustment axis
- **THEN** it is reported as intended with its purpose, and is not raised as a finding

### Requirement: Over-constraint names every responsible constraint

An over-constrained freedom SHALL be reported naming every constraint contributing to the
redundancy, not merely the count of excess constraints, because the finding is only
actionable if the engineer can see which interfaces compete. The report SHALL state the
consequence: that the redundant constraints either do nothing or deform the body, and that
which of those occurs depends on manufacturing variation rather than on design intent.

#### Scenario: The competing interfaces are named

- **WHEN** a plate is located by two dowels and clamped on a machined face that also
  constrains the same rotations
- **THEN** the result names the dowels and the face as jointly responsible for the
  redundant freedoms

#### Scenario: The consequence is stated, not implied

- **WHEN** an over-constraint is reported
- **THEN** the entry states that the outcome depends on manufacturing variation, so the
  finding is not read as a stylistic preference

### Requirement: Over-constraint marks the load path indeterminate and that travels

An over-constrained load path SHALL be marked indeterminate, and every downstream screen
consuming that path SHALL either carry the qualifier in its result or decline to report,
naming the indeterminacy. A strength, deflection, or alignment number computed across an
indeterminate path MUST NOT be rendered as an unqualified result, because the load
division among redundant constraints is not determined by the declared geometry.

#### Scenario: A confident stress on an indeterminate path is refused

- **WHEN** a bolt-shear screen runs on an over-constrained joint
- **THEN** the result either carries the indeterminacy qualifier naming the redundancy, or
  reports "not evaluated" for that reason — never a plain number with a citation

#### Scenario: The qualifier reaches the report and the bundle

- **WHEN** a qualified result is rendered or exported
- **THEN** the indeterminacy and its cause appear on the document, not only in metadata

#### Scenario: Resolving the redundancy clears the qualifier

- **WHEN** the declaration is changed to remove the redundant constraint
- **THEN** the downstream screens report unqualified results, and the change is visible in
  the diff between the two builds

### Requirement: Intentional redundancy is declared and justified, never assumed

A redundant constraint SHALL be accepted without a finding only when it is declared
intentional with a recorded justification and the mechanism that makes it tolerable — a
compliant interface, a controlled assembly sequence, a machining operation performed at
assembly. An undeclared redundancy SHALL remain a finding. The justification SHALL be
rendered wherever the constraint tally is rendered, so a reader can weigh it rather than
discovering only that the tool stayed quiet.

#### Scenario: A bolted flange face is a normal, declared case

- **WHEN** a flange face redundancy is declared intentional with its justification
- **THEN** the tally reports it as declared-intentional with the justification shown, and
  raises no finding

#### Scenario: Declaring it does not hide it

- **WHEN** an intentional redundancy is declared
- **THEN** the load path is still marked indeterminate if the declared mechanism does not
  determine the load division, so a declaration cannot silence a downstream qualifier it
  does not actually resolve

#### Scenario: Blank justification is refused

- **WHEN** a redundancy is declared intentional with no justification
- **THEN** the declaration is rejected naming the constraint
