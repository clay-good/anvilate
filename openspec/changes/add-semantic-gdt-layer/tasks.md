# Tasks: Semantic GD&T layer

## 1. Model

- [x] 1.1 Typed frame model (characteristic, value, modifiers, ordered datum references)
      with Y14.5/ISO 1101 vocabulary
- [x] 1.2 Validation rules: tag-graph resolution, characteristic/datum legality,
      modifier legality
- [x] 1.3 Position-tolerance contribution to 1D stack-ups with stated conversion method

## 2. Consumers

- [x] 2.1 Drawing feature-control-frame rendering from the model — `frame_drawing`
      in `anvilate.export.fcf`, written to DXF by
      `anvilate.export.dxf.export_feature_control_frame_dxf`
- [ ] 2.2 AP242 semantic PMI population path (spec-level contract; implementation lands
      with STEP export)
- [x] 2.3 QIF characteristic definition mapping — `qif_characteristic_mapping` in
      `anvilate.export.qif`, the layer that owns the QIF vocabulary

## 3. Tests & docs

- [x] 3.1 Legality-rule test matrix (valid/invalid frame combinations)
- [x] 3.2 Propagation test: one declaration change, three consumers update
- [x] 3.3 Documentation: supported characteristics and modifiers, and the screening scope

## Scope as shipped

Everything but 2.2, which waits on a STEP writer that does not exist. First the model and
its legality rules (1.1-1.3), the legality test matrix (3.1) and the documentation (3.3) —
`src/anvilate/gdt.py`, `examples/feature_control_frame_legality.py`, `docs/semantic-gdt.md`.

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

Since shipped: the drawing consumer (2.1) and the propagation test it unblocked (3.2).
`src/anvilate/export/fcf.py`, `examples/feature_control_frame_drawing.py`.

**Every geometric symbol is drawn as geometry, not typeset.** A ⌖ or an Ⓜ written into a
DXF as text renders only where the viewer has a font carrying the glyph; where it does not
the callout shows a missing-glyph box or silently loses its modifier, which crosses as a
looser requirement than the drawing states. Only the tolerance digits and the datum
letters stay text, and the permitted character set is closed because the frame's width
allowance was checked for those characters and nothing else.

**The proportions were read out of a published symbol chart** (Genium *Drafting Manual*
Section 6.1, February 1997, based on ASME Y14.5M-1994), which dimensions each symbol as a
multiple of the character height h — the same lesson as the QIF mapping above. Three would
have been wrong from memory: symmetry is three lines of 2h, 1.2h and 2h rather than an
equals sign; cylindricity's tangent lines stand at 60°; and Ø's 1.5h is the symbol's
height, not the slash's length. **The Ø was found by rendering a real frame and looking at
it**, not by a unit test — read as the length it draws a Ø barely taller than its own
circle, and every assertion still passed.

The symbol tests assert defining properties (tangency, the 30° angle, the 1.1h arrow
spacing) rather than bounding boxes the code produced, because a test whose expected
values come from the thing under test passes on its own drift.

**2.2 AP242 semantic PMI population is the one still open.** It waits on STEP export, as
the task itself says.

**2.3 QIF characteristic definition mapping.** It landed in
`anvilate.export.qif`, which owns the QIF schema decisions, once that module existed.
Every name in the mapping was read out of the published QIF 3.0 XSD rather than
recalled, and **three would have been guessed wrong**: QIF spells profile-of-a-line
`LineProfile`, its material-modifier enumeration is REGARDLESS/MAXIMUM/LEAST rather than
the drawing abbreviations, and the non-diametral zone element is `NonDiametricalZone` for
position but `PlanarZone` for the orientation characteristics. A modifier the target type
has no element for is **refused**, not dropped — six of the fourteen definition types
carry `MaterialCondition` and the rest do not, and a Ⓜ that vanishes on the way out
crosses as a tighter requirement than the drawing granted. It is a definition mapping and
not a document writer, because QIF's `DatumType` requires a `DatumDefinitionId` anchored
to a feature and a frame knows only the letter; what a caller still owes comes back in
`unresolved` rather than defaulted.

The drawing consumer renders the frame itself, not the leader, the datum feature symbol or
its placement on a part; those belong with the drawing-generation layer.
