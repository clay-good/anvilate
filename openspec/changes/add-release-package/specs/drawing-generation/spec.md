# Drawing Generation Specification (delta)

## ADDED Requirements

### Requirement: An assembly drawing for each product node

Every product and sub-product SHALL get an assembly drawing: projected and exploded
views, balloons numbered by the BOM's find numbers for that level, a parts list with find
number, part number, description and quantity, and a title block carrying the product's
part number and revision. Sub-products SHALL appear as one balloon on their parent's
drawing and be detailed on their own sheet. All drawings SHALL be gathered in one PDF.

#### Scenario: Balloons match the BOM

- **WHEN** the stage's assembly drawing and BOM are compared
- **THEN** every balloon number is a find number in the BOM at that level, with the same
  part number and quantity
