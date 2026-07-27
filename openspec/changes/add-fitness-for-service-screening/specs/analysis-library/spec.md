# Analysis Library Specification (delta)

## ADDED Requirements

### Requirement: Fracture screening set — SIF solutions, reference stress, FAD placement

The analysis library SHALL provide a fracture screening set under the library contract:
(a) named handbook stress intensity factor solutions (at minimum through-wall,
semi-elliptical surface, and embedded flaw geometries in plates and cylinders) each
citing its open-literature source and enforcing its stated geometric validity ranges —
out-of-range inputs report "not evaluated," never extrapolated; (b) reference-stress
plastic-collapse solutions for the same geometries; (c) failure assessment diagram
placement computing the assessment point (Kr, Lr) against the cited open-literature
Level-2-class FAD curve, with the verdict expressed as margin along the load line and
the cutoff Lr,max derived from the supplied material properties. Fracture toughness
SHALL be user-supplied with provenance; a Charpy-correlated toughness estimate MAY be
offered only with the correlation cited and the result labeled an estimate, consistent
with the derived-fatigue-parameter doctrine. Results SHALL carry the screening label and
a statement that flaw assessment dispositions require a qualified assessor; the library
MUST NOT reproduce API 579 Level-1 screening figures or exemption curves.

#### Scenario: Assessment point placed with margin

- **WHEN** a semi-elliptical surface flaw in a cylinder is assessed with user-supplied
  toughness and yield/tensile properties under a declared membrane stress
- **THEN** the result reports Kr, Lr, the FAD curve citation, the margin along the load
  line to the curve, and which failure mode (fracture-dominated, collapse-dominated, or
  interactive) the point sits in

#### Scenario: Validity range enforced

- **WHEN** a flaw's depth-to-thickness ratio falls outside the cited SIF solution's
  stated range
- **THEN** the check reports "not evaluated" naming the violated range — never an
  extrapolated K

#### Scenario: Estimated toughness is labeled

- **WHEN** toughness is derived from user-supplied Charpy energy via a cited correlation
- **THEN** the result carries the correlation citation and an estimate label, and the
  evidence bundle distinguishes it from directly supplied toughness

#### Scenario: Screening framing is non-negotiable

- **WHEN** any fracture screening result is rendered in a scorecard or report
- **THEN** it states the screening label and the qualified-assessor requirement, and no
  output phrase asserts fitness for continued service
