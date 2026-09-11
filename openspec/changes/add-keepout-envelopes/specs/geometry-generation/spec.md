# Geometry Generation Specification (delta)

## ADDED Requirements

### Requirement: Keepout envelopes are generated geometry, held separately

Declared keepout envelopes SHALL be generated as tagged B-Rep bodies through the same
pattern-constrained, sandboxed, deterministic mechanism as material geometry, from a
keepout archetype set meeting the pattern-library contribution contract; freestyle
generation of a keepout SHALL be disabled under the same default as freestyle part code.
Keepout bodies SHALL be held separately from the part solid and MUST NOT be unioned into
it, subtracted from it, or otherwise allowed to change the manufactured shape.

#### Scenario: Keepout is a body with a tag

- **WHEN** a spec declaring a beam-path cone is built
- **THEN** a tagged keepout body is generated and carried alongside the part solid, and
  the part solid's volume is unchanged by its presence

#### Scenario: Keepout cannot alter the part

- **WHEN** a keepout overlaps the part solid
- **THEN** the overlap is reported as an intrusion and the part solid is not modified —
  the system MUST NOT quietly subtract the keepout to make the check pass

#### Scenario: Regeneration is deterministic

- **WHEN** the same spec is rebuilt with pinned kernel versions
- **THEN** the keepout bodies regenerate identically, as the part geometry does

### Requirement: Swept volumes of declared motion are keepouts

The system SHALL be able to generate, as a keepout with its own tag, the swept volume of a
body over any motion the spec declares — a hinge range, a linear stroke, an adjustment
travel, a robot-flange path — so that clearance for motion is checked by the same
intrusion mechanism as static clearance rather than by a separate facility.

#### Scenario: Adjustment travel becomes protected space

- **WHEN** a spec declares an adjustment screw with a stated travel range
- **THEN** the swept volume of the moving element over that range is available as a
  keepout, tagged and checkable

#### Scenario: Undeclared motion is not invented

- **WHEN** a part has a moving feature whose range the spec does not state
- **THEN** no swept volume is generated and the scorecard names the motion as undeclared,
  rather than sweeping an assumed range
