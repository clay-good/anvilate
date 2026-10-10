# Change: More drawable parts — every common part an agent is asked for comes back as a picture and a STEP file

## Why

An engineer asks their agent for "a bracket for this motor" or "a lifting lug for 5 t" and
expects to see it and open it in their own CAD. Today four element types draw (base plate,
cover plate, transmission shaft, timber beam). Twenty-six others are checked but come back
"not drawn", and the most-requested everyday parts (angle brackets, flanges, spacers,
sheet-metal brackets) have no element at all.

Two things hold the catalog back, and adding parts one by one would not fix either:

- **The renderer is written per pattern.** It projects each pattern's known corners, and
  says so: it "refuses to masquerade as a general hidden-line renderer". Every new part
  needs new drawing code.
- **Holes, slots, fillets and chamfers are rebuilt inside each pattern.** A bracket, a
  flange and a lug all need the same hole, and each would get its own.

Anvilate is not a CAD system and this change does not make it one. The parts here are
parametric archetypes with declared bounds: quick, correct, and handed off as STEP.

## What Changes

| Area | Change |
| --- | --- |
| Shared features | One feature vocabulary every pattern uses: through hole, counterbore, countersink, slot, hole pattern (rectangular, bolt circle), fillet, chamfer. Each is a tagged, measurable feature. |
| General drawing | Views come from the built solid itself (hidden-line projection), so a new pattern draws with no drawing code. Hidden edges dashed; PNG and SVG from the same projection. |
| Dimensioned view | A view can carry the part's key dimensions, read from the built solid, so the agent and the engineer can check the picture against the request. |
| Parts already checked | Lifting lug, gusset plate, shear plate, tension member, shaft key, structural members (from the section tables), pipe run, bearing and spring envelopes, spur gear pair. |
| New everyday parts | Mounting plate, angle bracket, plate flange (bolt circle from the flange tables where a standard is named), spacer/bushing/standoff, shaft collar, stepped shaft with keyways, pulley, clevis, tube, extrusion profile, sheet-metal bracket (L, U, Z) with flat pattern, enclosure. |
| Catalog an agent can ask | One call lists what can be drawn, each with its parameters, bounds, face tags and outputs. |
| Honest gaps | A part outside the catalog is refused with the nearest patterns. A drawn part with no screen says "not evaluated". Site elements (footings, walls, piles, ventilation zones) stay undrawn, by decision. |

**Order of work.** No one publishes how often each part is requested, so the order follows
how the big catalogs (McMaster-Carr, MISUMI) organise what engineers buy most: flat
mounting plates and brackets first, then sheet-metal brackets, spacers and standoffs,
gussets, shafts, collars, flanges, lugs and clevises, sections, enclosures, pulleys, and
gears last. Gears come last on purpose: a June 2026 test of seven text-to-CAD tools found
gear geometry wrong in every tool that attempted it, so Anvilate draws a gear as its
pitch, root and tip circles and says so, rather than tooth flanks it cannot stand behind.
No tool in that test pairs the part with a cited check; that pairing is what this adds.

## Impact

- Affected specs: `geometry-generation` (ADDED, MODIFIED), `drawing-generation` (ADDED),
  `discipline-packs` (ADDED).
- Affected code (when implemented): `anvilate.geometry` (feature library, pattern
  registry, projector), `anvilate.raster`, new pack elements, MCP catalogue, examples.
- Sequenced before `add-part-combinations`, which places these parts together.
- Explicitly out: freeform or sketch-based modelling; surfacing; threads modelled as
  geometry (cosmetic only); involute tooth flanks to manufacturing accuracy; any editing
  UI. For anything past these archetypes the answer is the STEP file in the user's CAD.
