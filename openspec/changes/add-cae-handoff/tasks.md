# Tasks: CAE handoff

Depends on the meshing pipeline in `validation-gauntlet` T3 and on
`add-product-structure` (tagged interfaces and connections).

## 1. Decks

- [ ] 1.1 Keyword-format `.inp` writer: mesh, materials, sections, supports, loads by
      tagged face, steps per load case
- [ ] 1.2 Bulk-data `.bdf` writer with the same content, subcases per load case
- [ ] 1.3 Unit-system header and sidecar; refusal when a value cannot be expressed
- [ ] 1.4 Deck marked as unsolved input in the deck and in the bundle
- [ ] 1.5 Round-trip test: each deck parses in an open reader with the expected counts

## 2. Imports

- [ ] 2.1 Interface force reader for open result formats (grid-point forces,
      keyword-format result files), as an optional extra
- [ ] 2.2 Provenance per import: file hash, declared solver and version, case identity,
      coordinate system, units
- [ ] 2.3 Free-body equilibrium residual check
- [ ] 2.4 Region peak-value reads as cited inputs; disagreement findings

## 3. Screens

- [ ] 3.1 Joint and fitting screens accept imported loads
- [ ] 3.2 A docs page for CAE handoff: exporting a deck, importing loads, what a deck
      does and does not prove
