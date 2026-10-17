# Spec IR Specification (delta)

## ADDED Requirements

### Requirement: The product document is a published schema

The product document SHALL be a schema-validated document kind with a URN-identified
schema, versioned and migrated as the Design Spec is. It SHALL hold items with their
identity, instances and patterns, mates, the ground, an optional layout and optional
variants, every value with provenance. It SHALL reference sub-documents by relative path
or embed them; an unreadable reference SHALL be refused naming the path.

#### Scenario: A product round-trips

- **WHEN** a product document with a layout, a pattern and two variants is serialized and
  reloaded
- **THEN** it is identical, and its diff against the original is empty

#### Scenario: A missing sub-document

- **WHEN** a product references `drive/drive.product.yaml` and the file is absent
- **THEN** the product is refused naming the path and the item that references it
