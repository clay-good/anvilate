# Performance Budgets Specification (delta)

## ADDED Requirements

### Requirement: A budget is an allocated limit against itemized contributors

The system SHALL represent a performance budget as a typed record carrying: the budgeted
quantity and its allocated limit, an ordered set of contributors, the declared combination
rule, the computed total, and the margin against the limit. Every contributor SHALL carry
a name, a value with units, and its source — a scorecard check id, an imported
measurement, or a user declaration with provenance. The budget SHALL be dimensionally
consistent: every contributor and the allocated limit share one dimension, and a
contributor of a different dimension is rejected naming both.

#### Scenario: Budget is itemized, never a lump

- **WHEN** an angular line-of-sight budget is evaluated
- **THEN** the result lists each contributor with its value, unit, source, and share of
  the total, together with the rule, the total, and the margin

#### Scenario: Dimensional mismatch rejected

- **WHEN** a contributor expressed as a length is added to a budget allocated in
  milliradians
- **THEN** the budget is rejected naming the contributor, its dimension, and the expected
  dimension — rather than a number computed across incompatible quantities

### Requirement: The combination rule is declared and correlated terms are never RSS'd

A budget SHALL declare its combination rule explicitly; the system MUST NOT supply a
default. Supported rules SHALL be worst-case linear sum, root-sum-square, and a hybrid in
which contributors sharing a declared correlation group are summed before the groups are
combined in quadrature. Root-sum-square applied to contributors in the same correlation
group SHALL be refused, naming the group, because quadrature understates correlated terms.

#### Scenario: Undeclared rule is refused

- **WHEN** a budget is declared with contributors but no combination rule
- **THEN** the budget reports "not evaluated" naming the missing rule, rather than
  assuming one

#### Scenario: Correlated terms cannot hide in quadrature

- **WHEN** two contributors declare the same correlation group and the rule is
  root-sum-square
- **THEN** the budget is refused naming the group and the two contributors, and the hybrid
  rule is named as the applicable one

#### Scenario: Hybrid combines in the stated order

- **WHEN** a budget declares the hybrid rule with two correlation groups and three
  independent contributors
- **THEN** each group is summed, and the group sums and the independent contributors are
  combined in quadrature, with the intermediate group sums shown

### Requirement: A budget is a scorecard entry that can fail on passing parts

A budget SHALL emit a standard scorecard record whose measured value is the computed
total, whose threshold is the allocated limit, and whose entry names the governing
contributor — the one whose removal would most increase the margin. A budget MAY fail
while every contributing check passes, and the report SHALL make that outcome legible
rather than contradictory.

#### Scenario: All checks green, budget red

- **WHEN** every screen feeding a budget passes its own threshold and their combination
  exceeds the allocated limit
- **THEN** the scorecard carries a failing budget entry naming the governing contributor,
  and the card does not pass

#### Scenario: Governing contributor is named

- **WHEN** a budget is evaluated
- **THEN** the entry names the governing contributor and states its share of the total

### Requirement: An unevaluated contributor makes the budget unevaluated

A budget SHALL report "not evaluated" naming the contributor it waits on whenever any
contributor's source did not produce a value — its bound check reported "not evaluated,"
its measurement was not supplied, or its declaration is missing. A budget MUST
NOT be computed from the subset of contributors that happened to resolve, and MUST NOT
treat a missing contributor as zero.

#### Scenario: Missing contributor is not zero

- **WHEN** a thermal contributor's screen reports "not evaluated — material property
  missing"
- **THEN** the budget reports "not evaluated" naming that contributor, rather than a total
  computed from the remaining terms

#### Scenario: A declared but unallocated requirement is named

- **WHEN** a spec declares a top-level performance limit with no budget allocated against
  it
- **THEN** the scorecard carries a not-evaluated entry naming the limit and stating that
  no budget accounts for it

### Requirement: Contributors stay bound to the screens that produced them

A contributor sourced from a check SHALL store that check's id, and the budget SHALL
recompute when the bound check's result changes, so a budget cannot report a total derived
from a superseded screen. The evidence bundle SHALL record, per contributor, the source
identity and the value used.

#### Scenario: Budget follows its screens

- **WHEN** a design change alters a screen feeding a budget and the build is rerun
- **THEN** the budget total reflects the new value, and the bundle records which check
  produced it

#### Scenario: Broken binding is visible

- **WHEN** a contributor names a check id that no longer exists in the scorecard
- **THEN** the budget reports "not evaluated" naming the missing check id, rather than
  carrying a stale value

### Requirement: Headroom is reported as the inverse of the budget

Pairing with the library's forward-and-inverse doctrine, the system SHALL report, for an
evaluated budget, each contributor's headroom: the value that contributor could reach,
holding the others fixed under the declared rule, before the allocated limit is spent. A
headroom SHALL be reported as not available, naming the reason, where the rule makes it
undefined rather than reported as zero or unbounded.

#### Scenario: Headroom answers the design question

- **WHEN** an engineer asks how much more thermal drift the design can absorb
- **THEN** the budget reports that contributor's headroom in its own units under the
  declared rule

#### Scenario: Spent budget reports no headroom, honestly

- **WHEN** the total already exceeds the allocated limit
- **THEN** every headroom is reported as unavailable with the overrun stated, rather than
  as a negative allowance the reader might misread as slack

### Requirement: A contributor may be a budget, and nesting is bounded

A contributor SHALL be permitted to be another budget, evaluated under its own declared
combination rule, so that a system-level allocation can decompose into subsystem
allocations the way engineering practice already decomposes it. Nesting depth SHALL be
bounded and a cycle — a budget that reaches itself through its contributors — SHALL be
refused naming the cycle, rather than evaluated until the recursion stops it.

#### Scenario: Sub-budget keeps its own rule

- **WHEN** a system budget contains a subsystem budget whose rule differs from its parent's
- **THEN** the subsystem total is computed under its own rule and enters the parent as a
  single contributor, with both rules shown

#### Scenario: Cycle refused by name

- **WHEN** a budget's contributor chain reaches the budget itself
- **THEN** the budget is refused naming the cycle's members

### Requirement: Double counting is refused, not quietly summed

A budget SHALL refuse to include the same underlying quantity twice: a contributor derived
from another contributor SHALL declare that derivation, and two contributors resolving to
the same bound check id SHALL be refused naming both. Detection SHALL key on the bound
source identity rather than on contributor names, because the same quantity routinely
enters a budget under two labels.

#### Scenario: One check cannot contribute twice

- **WHEN** two contributors bind to the same check id
- **THEN** the budget is refused naming both contributors and the shared check

#### Scenario: A derived contributor declares its parent

- **WHEN** a contributor is computed from another contributor's value
- **THEN** the derivation is declared and the report shows it, so a reader can see the
  term is not independent

### Requirement: Contributors carry a basis, and growth allowance follows from it

Each contributor SHALL declare the basis of its value — measured, calculated, or estimated
— and a budget SHALL be able to apply a growth allowance per basis, following the
established practice that an estimated quantity carries more expected growth than a
measured one. The applied allowance SHALL be a margin-ledger entry of kind
contingency-or-growth, and a budget mixing bases SHALL report the share of its total that
rests on estimates.

#### Scenario: The budget says how much of it is guessed

- **WHEN** a budget's contributors are two measured and four estimated values
- **THEN** the result reports the share of the total resting on estimated values

#### Scenario: Growth allowance is ledgered, not folded in

- **WHEN** a growth allowance is applied to an estimated contributor
- **THEN** it appears as its own ledger entry with its basis stated, rather than being
  absorbed into the contributor's value

### Requirement: Compensating contributors are declared, never netted silently

A contributor SHALL be declared as compensating whenever its effect reduces the total — a
deliberate compensation, such as an athermalizing term of opposite sign — and the budget
SHALL report the total with and without it. A negative value MUST NOT be accepted as an
ordinary contributor, because a compensation that depends on a design feature surviving
review is not the same evidence as a term that cannot grow.

#### Scenario: Compensation is visible on both sides

- **WHEN** a budget includes a declared compensating term
- **THEN** the result reports the total with the compensation and the total without it

#### Scenario: A bare negative is refused

- **WHEN** a contributor is supplied with a negative value and no compensating declaration
- **THEN** the budget is refused naming the contributor

### Requirement: The allocated limit carries its own provenance

An allocated limit SHALL record where it came from — an external requirement with its
source, an allocation derived from a parent budget, or a working assumption — and the
budget result SHALL state it. A limit recorded as a working assumption SHALL render as
such wherever the budget renders, so that a margin against an assumed limit is never read
as a margin against a requirement.

#### Scenario: An assumed limit is labeled everywhere it appears

- **WHEN** a budget is allocated against a working assumption
- **THEN** every surface rendering the budget states that the limit is assumed

#### Scenario: A derived allocation names its parent

- **WHEN** a subsystem limit is derived from a system budget
- **THEN** the result names the parent budget and the allocation that produced the limit

### Requirement: The governing contributor is defined operationally, with ties reported

The governing contributor SHALL be defined as the one whose removal most increases the
margin under the budget's own declared rule, computed by evaluation rather than assumed
from the largest value, because the two do not coincide under every rule. Where two or
more contributors govern equally the result SHALL report them as tied, and where a rule
makes the notion undefined the result SHALL say so rather than naming an arbitrary term.

#### Scenario: Governance is computed under the declared rule

- **WHEN** a hybrid-rule budget is evaluated
- **THEN** the governing contributor is determined by re-evaluating the rule without each
  candidate, not by sorting contributor values

#### Scenario: Ties are reported as ties

- **WHEN** two contributors would recover equal margin
- **THEN** both are named, and neither is silently preferred
