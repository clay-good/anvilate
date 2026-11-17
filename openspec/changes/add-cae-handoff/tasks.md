# Tasks: CAE handoff

Depends on the meshing pipeline in `validation-gauntlet` T3 and on
`add-product-structure` (tagged interfaces and connections).

## 1. Decks

- [ ] 1.1 Keyword-format `.inp` writer: mesh, materials, sections, supports, loads by
      tagged face, steps per load case
      (a declared frame is written: one B33 per member, general sections, releases,
      supports, node, member and gravity loads, a step per frame; solid meshes and
      loads by tagged face wait on the meshing pipeline of `add-local-fea`)
- [ ] 1.2 Bulk-data `.bdf` writer with the same content, subcases per load case
      (the same frame deck in large-field bulk data: CBAR, PBAR, MAT1, SPC1, FORCE,
      MOMENT, PLOAD1, GRAV, a subcase per frame; solid meshes wait as in 1.1)
- [x] 1.3 Unit-system header and sidecar; refusal when a value cannot be expressed
- [x] 1.4 Deck marked as unsolved input in the deck and in the bundle
      (the deck's header and sidecar; the bundle lists each deck under `decks`, outside
      the roll-up, evidence-bundle schema 1.33.0)
- [x] 1.5 Round-trip test: each deck parses in an open reader with the expected counts
      (pyNastran reads the bulk data, meshio the keyword deck; both dev-only)

## 2. Imports

- [ ] 2.1 Interface force reader for open result formats (grid-point forces,
      keyword-format result files), as an optional extra
      (a CSV of grid-point forces on a free body is read; the solvers' native result
      files are not, and no solver is installed here to make one to test against)
- [x] 2.2 Provenance per import: file hash, declared solver and version, case identity,
      coordinate system, units
- [x] 2.3 Free-body equilibrium residual check
- [x] 2.4 Region peak-value reads as cited inputs; disagreement findings
      (from a CSV of case, region, quantity and value, like 2.1)

## 3. Screens

- [ ] 3.1 Joint and fitting screens accept imported loads
      (fastener patterns and fillet-weld groups do, case by case, with the import's
      provenance; lugs, fittings and bearings do not yet)
- [x] 3.2 A docs page for CAE handoff: exporting a deck, importing loads, what a deck
      does and does not prove
