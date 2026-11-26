# Tasks: Equipment anchorage

Builds on `src/anvilate/analysis/building_loads.py` and the anchorage screens in
`src/anvilate/packs/structural.py`.

## 1. Force

- [x] 1.1 Read ASCE 7-16 §13.3.1 and ASCE 7-22 §13.3.1 and record the equation forms,
      bounds and the vertical rule per edition ("anchor before implementing")
      — read from the two public US-government documents the editions came from; see
      design.md
- [x] 1.2 Component force with every coefficient user-supplied and cited; bounds applied
- [x] 1.3 Declared non-seismic lateral forces as load cases

## 2. Statics and anchors

- [x] 2.1 Overturning, uplift and sliding from mass, center of gravity, footprint and anchor
      pattern; per-anchor tension and shear for the governing direction
- [ ] 2.2 Existing anchorage screens on per-anchor forces; declared overstrength or
      ductility basis — **a build, not a wiring-up**: no concrete breakout or pullout
      screen exists yet; see design.md
- [ ] 2.3 Base frames through frame analysis when declared

## 3. Proof

- [x] 3.1 Worked example re-derived from a public worked example of the 7-22 equation
- [x] 3.2 A docs page for equipment anchorage: which coefficients are the user's
