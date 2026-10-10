# Tasks: More drawable parts

## 1. Foundations (everything else depends on these)

- [ ] 1.1 Pattern registry: one table of pattern, element type, parameter model, builder,
      tags and outputs; `build_spec`, the supported list and the catalog all read it
- [ ] 1.2 Shared feature library: through/blind hole, counterbore, countersink, slot,
      rectangular and bolt-circle patterns, fillet, chamfer; tagged and measurable
- [ ] 1.3 Refusals for features that do not fit (edge distance, overlap, oversize)
- [ ] 1.4 Move the four existing patterns onto the registry and feature library; volumes,
      tags and STEP bytes unchanged

## 2. General drawing

- [ ] 2.1 Hidden-line projector from the built solid (iso, front, top, right)
- [ ] 2.2 SVG and PNG from one projection; rasterizer vocabulary extended as needed
- [ ] 2.3 Regression: the four existing patterns draw the same edges as before
- [ ] 2.4 Dimensioned view: key dimensions measured from the solid, in the spec's units
- [ ] 2.5 Overview image: four views, name, overall size, material, verdict

## 3. Parts that are already screened

- [ ] 3.1 Lifting lug / padeye
- [ ] 3.2 Gusset plate, shear plate, tension member
- [ ] 3.3 Structural members from the section tables (I, channel, angle, HSS, tube, flat)
- [ ] 3.4 Shaft key; stepped shaft with shoulders and keyways (extends transmission shaft)
- [ ] 3.5 Pipe run
- [ ] 3.6 Catalog envelopes: rolling bearing, helical compression spring
- [ ] 3.7 Spur gear and gear pair (pitch, root, tip circles)

## 4. New everyday parts (element, schema, pattern, example each)

- [ ] 4.1 Angle bracket with screens (leg bending, bolt bearing, edge distance)
- [ ] 4.2 Mounting plate with holes and slots
- [ ] 4.3 Plate flange with bolt circle
- [ ] 4.4 Spacer, bushing, standoff, shaft collar
- [ ] 4.5 Pulley; clevis with pin screens
- [ ] 4.6 Tube and T-slot extrusion profile
- [ ] 4.7 Sheet-metal bracket (L, U, Z): formed solid, flat pattern, K-factor as input
- [ ] 4.8 Enclosure: box and lid shell

## 5. Catalog and honesty

- [ ] 5.1 Drawable-parts catalog generated from the registry; CLI and MCP surfaces
- [ ] 5.2 "Drawn, not screened" entry and unvalidated mark for patterns with no screen
- [ ] 5.3 Out-of-catalog refusal with nearest patterns and the STEP hand-off sentence
- [ ] 5.4 Gate: every registered pattern has an example spec, five golden tests, a catalog
      entry, and appears in the STEP referee job

## 6. Docs

- [ ] 6.1 Catalog page with one picture per pattern, generated
- [ ] 6.2 README and agent guide updated with the parts list
