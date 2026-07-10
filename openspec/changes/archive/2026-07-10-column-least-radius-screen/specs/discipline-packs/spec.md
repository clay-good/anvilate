# Discipline Packs Specification (delta)

## ADDED Requirements

### Requirement: Column screens use the least radius of gyration

Structural-pack buckling screens (columns and the axial term of beam-columns) SHALL compute slenderness from the least radius of gyration the declared cross-section carries, falling back to the bending-axis value only when the section records no transverse second moment; the flexural term of a beam-column SHALL continue to use the declared bending axis.

#### Scenario: Strong-axis declaration cannot inflate buckling capacity

- **WHEN** a column member is declared with a section whose bending axis is
  its strong axis (both second moments present)
- **THEN** the buckling screen computes slenderness from the weak-axis radius
  of gyration, and the scorecard reflects the weaker — governing — axis

#### Scenario: Hand-built sections keep the explicit contract

- **WHEN** a column member declares a `CrossSection` that carries no
  transverse second moment
- **THEN** the screen uses the bending-axis radius of gyration, as today, and
  the member documentation states the caller owns the weak-axis choice
