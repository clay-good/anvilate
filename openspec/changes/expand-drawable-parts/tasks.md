# Tasks: More drawable parts

## 1. Foundations (everything else depends on these)

- [x] 1.1 Pattern registry: one table of pattern, element type, parameter model, builder,
      tags and outputs; `build_spec`, the supported list and the catalog all read it
- [x] 1.2 Shared feature library: through/blind hole, counterbore, countersink, slot,
      rectangular and bolt-circle patterns, fillet, chamfer; tagged and measurable
- [x] 1.3 Refusals for features that do not fit (edge distance, overlap, oversize)
- [x] 1.4 Move the four existing patterns onto the registry and feature library; volumes,
      tags and STEP bytes unchanged
      — all four are on the registry. Only the cover plate has a feature, its bore, and it
      is now a tagged, measurable feature in the shared vocabulary. It is still cut by the
      pattern itself: cut by the feature library it is the same solid, but five lines of
      its STEP differ (the bore surface's origin sits 1 mm below the plate, where the shared
      tool starts), and the bytes are what this task holds. Measured 2026-10-10.

## 2. General drawing

- [x] 2.1 Hidden-line projector from the built solid (iso, front, top, right)
- [x] 2.2 SVG and PNG from one projection; rasterizer vocabulary extended as needed
- [x] 2.3 Regression: the four existing patterns draw the same edges as before
- [x] 2.4 Dimensioned view: key dimensions measured from the solid, in the spec's units
- [x] 2.5 Overview image: four views, name, overall size, material, verdict

## 3. Parts that are already screened

- [x] 3.1 Lifting lug / padeye (takes an optional `hole_height`, refused by name without it)
- [x] 3.2 Gusset plate, shear plate, tension member: each takes an optional `outline` (width,
      length, thickness, holes) and is drawn from it, refused when the outline cannot have
      the areas the element was screened on
- [x] 3.3 Structural members from the section tables: beam, column and beam-column from a
      named rolled I or H profile
- [x] 3.3b Flat-bar members: `section: FLAT 50x10`, breadth by depth, screened and drawn
- [x] 3.3c Hollow members named by their dimensions: a round tube, `section: TUBE 60x4`
      (outside diameter by wall), and a square-cornered box, `BOX 100x50x4` (breadth, depth,
      wall), screened and drawn; a wall that leaves no bore is refused by name
- [x] 3.3d Rolled HSS members, rectangular and round, from the fetched AISC workbook
      (`section: HSS6X4X1/4`, `HSS6.000X0.250`): computed from dimensions and design wall,
      drawn with their corners, and held to the workbook's tabulated properties on all 714
      rows where it is fetched
- [ ] 3.3h Channel and angle members, and pipe. A channel twists unless loaded through its
      shear centre and an angle bends about principal axes that are not its legs, neither of
      which the member screens model; the workbook's pipe areas disagree with their own
      dimensions by up to 3%
- [x] 3.3e A hollow beam is held to what its wall carries: `wall local buckling`, from the
      moment AISC 360-16 Chapter F gives a round tube (§F8) or a box (§F7), and NOT_EVALUATED
      past what those clauses cover. A section records the tube or box it is of
- [x] 3.3f A hollow column and beam-column: `wall slenderness`, passing while the wall is
      not a slender element (AISC 360 Table B4.1a) and NOT_EVALUATED past it, since the
      effective area of a slender wall (§E7) is not computed
- [ ] 3.3g §E7 effective area for a slender wall; and §F8's edition-difference entry, which
      waits on reading AISC's 360-22 comparison (the publisher refused the fetch on
      2026-10-10)
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
- [x] 4.9b Angle bracket screen: leg bending and bolt bearing under a load on the upright at a
      declared height (edge distance is not checked: its rule is a table not bundled)
- [x] 4.9c Stepped shaft: torsion at a shoulder, under a declared `torque`, with the
      stress-concentration factor the document states (`shoulder_stress_concentration`)
      against a declared `allowable_shear`. No factor is looked up: the element states no
      fillet, and no fillet-shoulder chart is in the library
- [x] 4.9d Stepped shaft: bending at a shoulder under a declared `bending_moment`, with its
      own stated factor and allowable, and the two peak stresses together when the shaft
      states a torque as well
- [ ] 4.9e Stepped shaft: a fillet radius per shoulder and the factor read from a published
      chart, solved out of the chart's own values before it is written, not recalled
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
