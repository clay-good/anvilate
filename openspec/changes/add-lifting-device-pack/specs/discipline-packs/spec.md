# Discipline Packs Specification (delta)

## ADDED Requirements

### Requirement: Below-the-hook lifting device pack

The system SHALL provide, when shipped, an optional below-the-hook lifting device pack
that designs and checks BTH-1-class lifters as typed devices: Design Category (A or B)
and Service Class (0–4) SHALL be typed spec inputs that resolve the nominal design factor
and fatigue-evaluation obligation with the governing clause cited; member checks
(tension, compression, bending, combined stress, and stability) SHALL be evaluated in
BTH-1 allowable-stress form; pin-connected plate checks SHALL compose the existing lug
limit states under BTH-1 design factors rather than duplicating them; and every check
SHALL cite its BTH-1 clause. Rated load, Design Category, and Service Class SHALL appear
in the evidence bundle and any generated drawing title block, because BTH-1 lifters must
be marked with them.

#### Scenario: Design category resolves the design factor

- **WHEN** a spreader beam is specified as Design Category B, Service Class 2
- **THEN** all strength checks apply the Category B design factor with the clause cited,
  and the scorecard states the category, class, and factor used

#### Scenario: Lug checks reuse the existing limit states

- **WHEN** the lifter's pin-connected plates are checked
- **THEN** the pack evaluates the already-specified lug limit states (net-section
  tension, shear-out, bearing, pin shear, weld) with BTH-1 design factors and citations,
  and does not report a second, conflicting set of lug results

#### Scenario: Service class gates fatigue

- **WHEN** the device's Service Class requires fatigue evaluation
- **THEN** a fatigue screen runs against the declared load cycles, and if the stress
  category or cycle data needed is not declared, the fatigue check reports "not
  evaluated" naming the missing input — never a silent pass

#### Scenario: Rated load travels to artifacts

- **WHEN** a validated lifter is exported
- **THEN** the rated load, Design Category, and Service Class appear in the evidence
  bundle and in the drawing title block fields designated for them
