# Validation Gauntlet Specification (delta)

## ADDED Requirements

### Requirement: T0 keepout intrusion check

T0 SHALL check every generated keepout against the part solid and against every other
body in the assembly that is not itself a keepout. Material intersecting a keepout's
protected core SHALL fail, and the scorecard entry SHALL name the intruding semantic tag,
the keepout's tag and reason, the intersection volume, and the worst penetration depth.
Material entering the declared clearance margin without reaching the core SHALL warn with
the remaining clearance stated. A declared keepout that was not generated, or that was
generated and not checked, SHALL report "not evaluated" naming the keepout.

#### Scenario: A stiffening rib intrudes and the card fails

- **WHEN** a rib added to resolve a deflection failure crosses a declared beam-path
  keepout
- **THEN** the card fails with an intrusion entry naming the rib's tag, the keepout's tag
  and reason, the intruded volume, and the penetration depth

#### Scenario: Margin intrusion warns rather than passes

- **WHEN** a boss stops 0.3 mm inside a keepout's declared 0.5 mm clearance margin without
  reaching the protected core
- **THEN** the entry is a warning stating the remaining clearance, not a pass

#### Scenario: Unchecked keepout is named

- **WHEN** a declared keepout is not generated because its archetype is unavailable
- **THEN** the scorecard carries a not-evaluated entry naming the keepout and the reason,
  and the card does not pass

#### Scenario: Intrusion carries a repair hint

- **WHEN** an intrusion fails
- **THEN** the failure carries a typed repair hint naming the intruding feature and the
  parameter whose change would clear the volume, in the form the repair loop consumes

### Requirement: A clean intrusion result states what it looked at

An intrusion result reporting no violation SHALL state the number of keepouts screened,
the number of bodies each was screened against, and the smallest clearance found with the
feature and keepout that produced it. A result MUST NOT render "no intrusion" in a form
indistinguishable from a run in which nothing was screened, and a build in which zero
keepouts were generated SHALL say so explicitly rather than reporting a clean check.

#### Scenario: Clean means measured

- **WHEN** a part with three keepouts passes the intrusion check
- **THEN** the entry states three keepouts screened, the bodies compared, and the smallest
  clearance found with the tags that produced it

#### Scenario: Nothing screened is not a pass

- **WHEN** a build generates no keepouts
- **THEN** the intrusion check reports that no keepouts were screened, rather than a clean
  verdict

### Requirement: The intrusion verdict is at nominal geometry and says so

An intrusion verdict SHALL state that it is computed on nominal geometry, without the
declared dimensional tolerances applied, until tolerance-aware intrusion ships. A
clearance smaller than the sum of the declared tolerances bearing on it SHALL be reported
as a warning naming that comparison, so a nominal pass with no real clearance is not
mistaken for a safe one.

#### Scenario: Nominal basis is stated

- **WHEN** an intrusion result is rendered
- **THEN** it states that the check is at nominal geometry

#### Scenario: Clearance inside the tolerance band warns

- **WHEN** the smallest clearance is smaller than the declared tolerances bearing on it
- **THEN** the result warns naming the clearance and the tolerances, rather than passing
  silently
