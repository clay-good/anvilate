# Tasks: Semantic GD&T layer

## 1. Model

- [ ] 1.1 Typed frame model (characteristic, value, modifiers, ordered datum references)
      with Y14.5/ISO 1101 vocabulary
- [ ] 1.2 Validation rules: tag-graph resolution, characteristic/datum legality,
      modifier legality
- [ ] 1.3 Position-tolerance contribution to 1D stack-ups with stated conversion method

## 2. Consumers

- [ ] 2.1 Drawing feature-control-frame rendering from the model
- [ ] 2.2 AP242 semantic PMI population path (spec-level contract; implementation lands
      with STEP export)
- [ ] 2.3 QIF characteristic definition mapping

## 3. Tests & docs

- [ ] 3.1 Legality-rule test matrix (valid/invalid frame combinations)
- [ ] 3.2 Propagation test: one declaration change, three consumers update
- [ ] 3.3 Documentation: supported characteristics and modifiers, and the screening scope
