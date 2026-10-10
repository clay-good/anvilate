# Tasks: More drawable parts

## 1. Foundations (everything else depends on these)

- [x] 1.1 Pattern registry: one table of pattern, element type, parameter model, builder,
      tags and outputs; `build_spec`, the supported list and the catalog all read it
- [x] 1.2 Shared feature library: through/blind hole, counterbore, countersink, slot,
      rectangular and bolt-circle patterns, fillet, chamfer; tagged and measurable
- [x] 1.3 Refusals for features that do not fit (edge distance, overlap, oversize)
- [ ] 1.4 Move the four existing patterns onto the registry and feature library; volumes,
      tags and STEP bytes unchanged

## 2. General drawing

- [x] 2.1 Hidden-line projector from the built solid (iso, front, top, right)
- [x] 2.2 SVG and PNG from one projection; rasterizer vocabulary extended as needed
- [x] 2.3 Regression: the four existing patterns draw the same edges as before
- [x] 2.4 Dimensioned view: key dimensions measured from the solid, in the spec's units
- [x] 2.5 Overview image: four views, name, overall size, material, verdict

## 3. Parts that are already screened

- [ ] 3.1 Lifting lug / padeye
- [ ] 3.2 Gusset plate, shear plate, tension member
- [ ] 3.3 Structural members from the section tables (I, channel, angle, HSS, tube, flat)
- [ ] 3.4 Shaft key; stepped shaft with shoulders and keyways (extends transmission shaft)
- [ ] 3.5 Pipe run
- [ ] 3.6 Catalog envelopes: rolling bearing, helical compression spring
- [ ] 3.7 Spur gear and gear pair (pitch, root, tip circles)

## 4. New everyday parts (element, schema, pattern, example each)

- [x] 4.1 Angle bracket: two legs, holes and slots per leg, optional stiffening rib
- [x] 4.2 Mounting plate with holes and slots
- [x] 4.3 Plate flange with bolt circle
- [x] 4.4 Spacer, bushing, standoff, shaft collar
- [x] 4.5 Pulley; clevis with pin hole; stepped shaft with keyways and end chamfers
- [x] 4.6 Tube and T-slot extrusion profile
- [x] 4.7 Sheet-metal bracket (L, U, Z): formed solid, developed length, K-factor as input
- [x] 4.8 Enclosure: open box shell with floor holes
- [ ] 4.9 Screens: angle bracket (leg bending, bolt bearing, edge distance), clevis (pin
      shear and bearing), stepped shaft (stress at a shoulder)
- [ ] 4.10 Sheet-metal flat pattern as a DXF with bend lines; minimum bend radius reported
      through the existing bend-radius screen
- [ ] 4.11 Enclosure lid

## 5. Catalog and honesty

- [x] 5.1 Drawable-parts catalog generated from the registry; CLI and MCP surfaces
- [x] 5.2 "Drawn, not screened" entry and unvalidated mark for patterns with no screen
- [x] 5.3 Out-of-catalog refusal with nearest patterns and the STEP hand-off sentence
- [ ] 5.4 Gate: every registered pattern has an example spec, five golden tests, a catalog
      entry, and appears in the STEP referee job

## 6. Docs

- [x] 6.1 Catalog page with one picture per pattern, generated
- [ ] 6.2 README and agent guide updated with the parts list
