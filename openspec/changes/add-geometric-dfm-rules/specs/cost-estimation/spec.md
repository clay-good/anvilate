# Cost Estimation Specification (delta)

## ADDED Requirements

### Requirement: Sheet metal, molding and casting cost screens

The system SHALL estimate screening-grade cost for sheet-metal parts (blank area, cut
length, bend count, setups), injection-molded parts (a tooling estimate from projected
area, cavities and side actions, plus piece price from cycle time and material), and
die-cast parts (tooling and piece price), each with its inputs, rates and sources shown.
Rates SHALL be user-supplied or labeled defaults.

#### Scenario: Tooling and piece price split

- **WHEN** a molded housing is estimated at a declared annual volume of 50,000
- **THEN** the estimate shows tooling and piece price separately, their basis, and the
  amortized unit cost at that volume

#### Scenario: A DFM change shows its cost effect

- **WHEN** an agent removes a side action by redesigning an undercut
- **THEN** the next estimate shows the tooling difference with the side action named
