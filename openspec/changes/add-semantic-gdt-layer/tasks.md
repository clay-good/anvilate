# Tasks: Semantic GD&T layer

## 1. Model

- [x] 1.1 Typed frame model (characteristic, value, modifiers, ordered datum references)
      with Y14.5/ISO 1101 vocabulary
- [x] 1.2 Validation rules: tag-graph resolution, characteristic/datum legality,
      modifier legality
- [x] 1.3 Position-tolerance contribution to 1D stack-ups with stated conversion method

## 2. Consumers

- [ ] 2.1 Drawing feature-control-frame rendering from the model
- [ ] 2.2 AP242 semantic PMI population path (spec-level contract; implementation lands
      with STEP export)
- [ ] 2.3 QIF characteristic definition mapping

## 3. Tests & docs

- [x] 3.1 Legality-rule test matrix (valid/invalid frame combinations)
- [ ] 3.2 Propagation test: one declaration change, three consumers update
- [x] 3.3 Documentation: supported characteristics and modifiers, and the screening scope

## Scope as shipped

The model and its legality rules (1.1-1.3), the legality test matrix (3.1) and the
documentation (3.3). `src/anvilate/gdt.py`, `examples/feature_control_frame_legality.py`,
`docs/semantic-gdt.md`.

**The edition turned out to be load-bearing, not metadata.** ASME Y14.5-2018 eliminated
concentricity and symmetry — median-point controls that position or runout expresses
better — so the two editions do not share a characteristic set. `Y14Edition` is a declared
input and a 2018 frame using either is refused with the reason; the same callout builds on
the 2009 edition. That is the difference between a legacy callout and a mistake, and it
connects directly to `add-standards-effectivity`.

**The stack conversion states its method, because it is a choice.** A position zone of
total width t contributes ±t/2 to a 1D stack in any single direction, diametral or not.
That is worst case and the docstring says so: feeding it to an RSS or Monte Carlo stack as
a 1D uniform band overstates the spread and gives a number that is neither worst case nor
statistical. Bonus tolerance is refused on an RFS frame outright — not a conservative
simplification, just tolerance the drawing did not grant.

Still open, all three because they wait on a consumer that does not exist yet:

- **2.1 drawing feature-control-frame rendering.** `render()` produces the frame as text
  (`⌖ | Ø0.2 mm Ⓜ | A | B Ⓜ | C`), which is the model half. Drawing it into a DXF belongs
  with the drawing-generation layer.
- **2.2 AP242 semantic PMI population.** Waits on STEP export, as the task itself says.
- **2.3 QIF characteristic definition mapping.** Belongs with
  `add-quality-evidence-interchange`, which owns the QIF schema decisions.
- **3.2 propagation test (one declaration, three consumers).** There are no three
  consumers yet; it lands with the first of them.
