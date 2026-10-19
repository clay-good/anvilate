# Artifact Export Specification (delta)

## ADDED Requirements

### Requirement: IFC export of structural elements with their verdicts

The export layer SHALL export structural-pack elements, and products containing them, as
IFC: one element per part in the class and predefined type its archetype maps to, a
material association, the product tree as aggregation with transforms preserved and part
numbers as element tags, a standard profile definition with an extrusion for a member on
a standard section and a boundary representation otherwise, the schema's common property
sets where defined, and one Anvilate property set carrying part number, revision,
material, mass, validation status, the card digest and the design basis. IFC4 SHALL be the
default schema and IFC 4.3 a declared option; a capability the writer cannot provide for
the declared schema SHALL be refused naming it. The export gate and the unvalidated
watermark SHALL apply, with the watermark in the file header and in the property set. An
archetype with no mapping SHALL be refused naming it, never exported as a proxy.

#### Scenario: A base plate keeps its identity

- **WHEN** a validated base plate with its anchors is exported as IFC and opened in an
  IFC-conformant tool
- **THEN** it appears as a plate of the base-plate type with its material, mass, part
  number, validation status and card digest readable as properties, and each anchor as a
  mechanical fastener

#### Scenario: A rolled member keeps its section

- **WHEN** a W-shape beam is exported
- **THEN** the file carries the standard profile definition and an extrusion, and the
  receiving tool reports the section rather than a faceted solid

#### Scenario: Unvalidated is written on the element

- **WHEN** an unvalidated mezzanine beam is exported with the override
- **THEN** the file header and the element's property set both carry the unvalidated
  watermark

### Requirement: IFC exports are schema-checked and compared with the built solids

Every IFC export SHALL be validated against its declared schema with an open checker, and
CI SHALL re-read each exported file and compare every element's volume and centroid with
the built solid it came from within the tolerances the STEP validation properties use; a
mismatch SHALL fail the build naming the element.

#### Scenario: A silent geometry drop is caught

- **WHEN** a writer change leaves an element without geometry
- **THEN** the re-read comparison fails naming the element and the file
