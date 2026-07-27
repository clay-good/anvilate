# Tolerance Management Specification (delta)

## ADDED Requirements

### Requirement: Typed semantic GD&T model

Geometric tolerance declarations SHALL be represented in a typed semantic model using ASME Y14.5 / ISO 1101 vocabulary: feature control frames carrying the characteristic symbol, tolerance value, material-condition and other modifiers, and an ordered datum reference frame; datum features and toleranced features SHALL resolve against the semantic tag graph, and declarations referencing nonexistent tags or dimensionally invalid combinations (e.g., a flatness with a datum reference) MUST be rejected with the violation named.

#### Scenario: Position with MMC validates

- **WHEN** a spec declares a position tolerance at maximum material condition on a tagged hole pattern referencing datums A, B, C
- **THEN** the model stores the frame with its symbol, value, modifier, and ordered datum references, each datum resolved to a real tagged feature

#### Scenario: Invalid frame rejected

- **WHEN** a declaration attaches a datum reference to a form tolerance that permits none
- **THEN** validation rejects it naming the characteristic and the rule violated, before any downstream consumer renders it

#### Scenario: Position tolerance feeds the stack-up

- **WHEN** a declared position tolerance governs a hole in a user-declared dimension chain
- **THEN** the stack-up analysis can consume its positional contribution, with the conversion method stated in the result

### Requirement: One GD&T model, three consumers

The semantic GD&T model SHALL be the single source for every surface that expresses geometric tolerances: drawing feature control frames, STEP AP242 semantic PMI on export, and QIF characteristic definitions in quality interchange; consumers MUST render from the model rather than duplicating tolerance data, so a declaration change propagates to all three without drift.

#### Scenario: Change propagates everywhere

- **WHEN** the user tightens a position tolerance in the spec
- **THEN** the regenerated drawing frame, the exported semantic PMI, and the QIF characteristic all carry the new value from the same model, with no surface showing the stale tolerance
