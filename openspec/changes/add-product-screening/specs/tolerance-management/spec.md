# Tolerance Management Specification (delta)

## ADDED Requirements

### Requirement: A stack-up chain may run through a product's connections

A one-dimensional tolerance chain SHALL be declarable across items of a product: each link
either a toleranced dimension of a part, addressed by item path and tag, or a connection,
contributing its fit or position allowance. The chain SHALL be evaluated worst-case and
root-sum-square, and by seeded Monte Carlo when declared, with each link's contribution
reported. A link whose part carries no tolerance SHALL take the general tolerance and say
so.

#### Scenario: Carriage height through four parts

- **WHEN** a chain runs from the base plate through a rail, a carriage and a top plate to
  the tool face
- **THEN** the stack reports worst-case and RSS ranges, each part's contribution, and the
  governing link
