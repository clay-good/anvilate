# Discipline Packs Specification (delta)

## ADDED Requirements

### Requirement: Equipment anchorage screen in the structural pack

The structural pack SHALL provide, when shipped, an equipment anchorage element: a piece
of equipment with a declared mass, center of gravity, footprint and anchor pattern, loaded
by a horizontal seismic design force computed from the nonstructural-component equation
of the declared code edition — with every tabulated coefficient user-supplied with its
table citation, the equation's lower and upper bounds applied and cited, and the vertical
component by the cited rule — and by any declared non-seismic lateral force. The screen
SHALL compute overturning, uplift and sliding by statics and the tension and shear on each
anchor for the governing direction without relying on friction, and SHALL run the
existing concrete anchorage screens on those forces under the overstrength or ductility
basis the document declares. A coefficient not supplied SHALL leave the force not
evaluated naming it; the pack MUST NOT bundle the standard's coefficient tables.

#### Scenario: A chiller on four anchors

- **WHEN** a 2,400 kg chiller on four cast-in anchors is declared with its coefficients
  cited to the declared edition's tables and a center of gravity 900 mm above the slab
- **THEN** the card reports the component force with its bounds, the governing anchor's
  tension and shear, and each anchor check with its clause, naming the edition the
  equation came from

#### Scenario: A coefficient from memory is refused

- **WHEN** the document supplies a component coefficient with no table citation
- **THEN** the force is not evaluated naming the coefficient and the table it must cite

#### Scenario: The edition changes the equation

- **WHEN** the same equipment is screened under design bases pinning ASCE 7-16 and
  ASCE 7-22
- **THEN** each card computes the force by its own edition's equation and names it, and the
  edition-difference report states both forces
