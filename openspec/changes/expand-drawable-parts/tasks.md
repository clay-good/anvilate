# Tasks: More drawable parts

## 1. Foundations (everything else depends on these)

- [x] 1.1 Pattern registry: one table of pattern, element type, parameter model, builder,
      tags and outputs; `build_spec`, the supported list and the catalog all read it
- [x] 1.2 Shared feature library: through/blind hole, counterbore, countersink, slot,
      rectangular and bolt-circle patterns, fillet, chamfer; tagged and measurable
- [x] 1.3 Refusals for features that do not fit (edge distance, overlap, oversize)
- [ ] 1.4 Move the four existing patterns onto the registry and feature library; volumes,
      tags and STEP bytes unchanged
      — all four are on the registry. Only the cover plate has a feature, its bore. Cut
      through the feature library it is the same solid at the same volume and tags, but
      five lines of its STEP differ (the bore surface's origin sits 1 mm below the plate,
      where the shared tool starts). Held open: "STEP bytes unchanged" has to give, or the
      bore stays its own cut. Measured 2026-10-10.

## 2. General drawing

- [x] 2.1 Hidden-line projector from the built solid (iso, front, top, right)
- [x] 2.2 SVG and PNG from one projection; rasterizer vocabulary extended as needed
- [x] 2.3 Regression: the four existing patterns draw the same edges as before
- [x] 2.4 Dimensioned view: key dimensions measured from the solid, in the spec's units
- [x] 2.5 Overview image: four views, name, overall size, material, verdict

## 3. Parts that are already screened

- [x] 3.1 Lifting lug / padeye (takes an optional `hole_height`, refused by name without it)
- [ ] 3.2 Gusset plate, shear plate, tension member: each declares areas and no outline, so
      each needs outline fields before it can be drawn
- [x] 3.3 Structural members from the section tables: beam, column and beam-column from a
      named rolled I or H profile
- [ ] 3.3b Channel, angle, HSS and flat-bar members (no bundled table yet)
- [x] 3.4 Shaft key; stepped shaft with shoulders and keyways
- [x] 3.5 Pipe run: drawn straight from an optional `designation` (NPS and schedule), and
      refused when the declared bore is not that pipe's
- [x] 3.6 Catalog envelopes: rolling bearing (by designation), helical compression spring
- [x] 3.7 Spur gear pair as tip cylinders, with pitch, root and tip circles stated

## 4. New everyday parts (element, schema, pattern, example each)

- [x] 4.1 Angle bracket: two legs, holes and slots per leg, optional stiffening rib
- [x] 4.2 Mounting plate with holes and slots
- [x] 4.3 Plate flange with bolt circle
- [x] 4.4 Spacer, bushing, standoff, shaft collar
- [x] 4.5 Pulley; clevis with pin hole; stepped shaft with keyways and end chamfers
- [x] 4.6 Tube and T-slot extrusion profile
- [x] 4.7 Sheet-metal bracket (L, U, Z): formed solid, developed length, K-factor as input
- [x] 4.8 Enclosure: open box shell with floor holes
- [x] 4.9a Clevis screen: pin shear, ear bearing, ear net tension and ear shear-out under a
      declared pin load, each against a declared allowable
- [ ] 4.9b Screens: angle bracket (leg bending, bolt bearing, edge distance), stepped shaft
      (stress at a shoulder)
      — held open, 2026-10-10: a shoulder needs its stress-concentration factor, and no
      fillet-shoulder Kt is in the library; it is to be solved out of a published chart
      before it is written, not recalled. The bracket's checks need the load's direction
      and where on the upright it acts, which the element does not yet say.
- [x] 4.10 Flat profiles as DXF: mounting plate, flange, lug, and a sheet-metal bracket's
      developed blank with its bend lines
- [x] 4.10b Minimum bend radius reported through the existing bend-radius screen
- [x] 4.11 Enclosure lid: a plate with holes and an optional lip that drops into the box

## 5. Catalog and honesty

- [x] 5.1 Drawable-parts catalog generated from the registry; CLI and MCP surfaces
- [x] 5.2 "Drawn, not screened" entry and unvalidated mark for patterns with no screen
- [x] 5.3 Out-of-catalog refusal with nearest patterns and the STEP hand-off sentence
- [x] 5.4 Gate: every registered pattern has an example spec, five golden tests, a catalog
      entry, and appears in the STEP referee job (`tests/test_pattern_gate.py`, read from
      the registry; the referee's floor is the registry's size)

## 6. Docs

- [x] 6.1 Catalog page with one picture per pattern, generated
- [x] 6.2 README and agent guide updated with the parts list
