# Assembly Feasibility Specification (delta)

## ADDED Requirements

### Requirement: Tool access is screened as a swept envelope, in the state it happens in

A screen SHALL evaluate, for every declared fastener and adjustment, whether its required
tool envelope can reach the feature along the declared approach direction, by generating
the swept tool volume as a keepout and checking it with the existing intrusion mechanism
rather than a second collision implementation. Access SHALL be evaluated in each declared
assembly state in which the operation occurs, because a feature reachable on the bare part
is not necessarily reachable in the assembly. A feature declared with no tool or no
approach direction SHALL report "not evaluated" naming what is missing.

#### Scenario: The head clears and the driver does not

- **WHEN** a cap screw's head has clearance but its driver envelope intersects an adjacent
  boss along the declared approach
- **THEN** the screen fails naming the fastener, the tool, the intersecting feature, and
  the state

#### Scenario: Access is a question about a state

- **WHEN** a fastener is reachable in the sub-assembly state and blocked in the closed
  state where it is actually installed
- **THEN** the screen evaluates the state the operation is declared to occur in and fails
  if that state blocks it

#### Scenario: Undeclared approach is not assumed

- **WHEN** a fastener declares no approach direction
- **THEN** the screen reports "not evaluated" naming the fastener, rather than choosing a
  convenient direction

### Requirement: Swing arc is screened against the clearance actually available

A screen SHALL report the angular arc a declared tool can sweep at each feature against
the arc its operation requires, so that a tool which fits but cannot turn is caught. The
result SHALL state the arc achieved and the arc required, and where a ratcheting or
limited-swing tool is declared, the required arc SHALL be taken from that tool's
declaration rather than assumed.

#### Scenario: It fits but it cannot turn

- **WHEN** a wrench fits over a fastener but can sweep only a few degrees before striking
  a wall
- **THEN** the screen fails reporting the achieved and required arcs and naming the wall

#### Scenario: The tool's own limits are used

- **WHEN** a ratcheting driver with a declared minimum arc is specified
- **THEN** the required arc comes from that declaration

### Requirement: A valid assembly order exists, or the blocking parts are named

A screen SHALL determine whether a valid assembly order exists given each part's declared
insertion direction and the features it occupies, and SHALL report either a valid order or
the set of parts that block one another with the conflict named. A circular blocking
relationship SHALL be reported naming every member of the cycle, and a part with no
declared insertion direction SHALL report "not evaluated" naming the part rather than
being treated as insertable from anywhere.

#### Scenario: No valid order is a finding, not a silence

- **WHEN** three parts each require insertion along a path another already occupies
- **THEN** the screen fails naming all three and the conflict, rather than reporting
  nothing

#### Scenario: A valid order is reported as a result

- **WHEN** a valid order exists
- **THEN** it is reported, so the finding is distinguishable from an unscreened assembly

### Requirement: Adjustable and serviceable features stay reachable when they are used

A feature declared adjustable or serviceable SHALL be screened for reachability in the
assembly state in which that adjustment or service occurs, and an enclosure whose closure
makes a declared adjustment unreachable SHALL be a finding naming the adjustment and the
closing part. Where a spec declares that alignment occurs after closure, the screen SHALL
evaluate access through whatever port, window, or tool path the spec declares, and report
"not evaluated" naming the access route if none is declared.

#### Scenario: Sealed and unalignable

- **WHEN** an internal adjustment is declared to be set after the housing closes, and the
  closed state offers no declared access route
- **THEN** the screen fails naming the adjustment and the closing part

#### Scenario: A declared port is screened, not assumed adequate

- **WHEN** an access port is declared for a post-closure adjustment
- **THEN** the tool envelope is swept through that port and the verdict follows from the
  geometry

### Requirement: A tolerance nobody can measure is reported

A screen SHALL report any toleranced dimension that cannot be measured in any declared
assembly state with the declared inspection method, naming the dimension and the states
examined. The system MUST NOT treat an unmeasurable tolerance as satisfied by the
dimensional screens alone, because a control nobody can verify on the built article is a
drawing note rather than a control, and the verification matrix should say so.

#### Scenario: An internal dimension has no measurable state

- **WHEN** a toleranced internal dimension is enclosed in every declared assembly state
- **THEN** the screen reports it as unmeasurable naming the dimension and the states, and
  the verification matrix records it as such

#### Scenario: The report names what it examined

- **WHEN** the inspectability screen finds nothing unmeasurable
- **THEN** it states the number of toleranced dimensions and states examined, so a clean
  result is distinguishable from an unrun one
