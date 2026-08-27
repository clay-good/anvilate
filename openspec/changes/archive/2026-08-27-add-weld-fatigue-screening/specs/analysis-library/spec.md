# Analysis Library Specification (delta)

## ADDED Requirements

### Requirement: Weld fatigue screening from a declared detail category

The analysis library SHALL provide nominal-stress weld fatigue screening in which the
detail category is a typed user-supplied input carrying the standard, edition, and
detail description it came from; the library MUST NOT infer a detail category from
geometry, and a check without a declared category SHALL report "not evaluated." From the
declared category the library SHALL construct the standardized S-N curve using cited
slope, constant-amplitude limit, and cutoff conventions, apply thickness/size and
mean-stress corrections only when their inputs are declared, and report every applied
correction with its factor and citation. Cumulative damage over a declared stress-range
spectrum SHALL compose the existing linear-damage summation, and an allowable-cycles (or
allowable stress range for a target life) design inverse SHALL pair with the forward
check per the library contract.

#### Scenario: Category drives a cited curve

- **WHEN** a user declares a detail category with its source and a constant-amplitude
  stress range and cycle count
- **THEN** the check reports the damage fraction, the constructed curve's slopes and knee
  points with citations, and the declared category's source in provenance

#### Scenario: No category, no verdict

- **WHEN** a welded joint is checked without a declared detail category
- **THEN** the check reports "not evaluated" naming the missing category — the library
  never selects one from the joint geometry

#### Scenario: Corrections are visible

- **WHEN** plate thickness exceeds the reference thickness and a thickness correction
  applies
- **THEN** the result states the correction factor, its citation, and the corrected
  category value alongside the declared one

#### Scenario: Spectrum damage and inverse agree

- **WHEN** a variable-amplitude spectrum yields a damage fraction below 1.0 and the
  allowable-cycles inverse is queried for the same detail and stress range
- **THEN** the forward and inverse results are mutually consistent under the library's
  round-trip requirement
