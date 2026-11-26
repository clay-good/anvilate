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
- [x] 2.3 Base frames through frame analysis when declared
      (`anchorage.frame_anchor_demand`: each solved support reaction is one anchor's
      demand, uplift being a negative vertical reaction and the shear the resultant of the
      two horizontal ones. It reproduces the rigid-base route to the last digit on a
      four-support skid, which cross-checks both; what it adds is that the centre of
      gravity, the resultant and the height are derived from the declaration instead of
      being told. A support declaring a rotational restraint is named, because a bolt is a
      pin — taken from the declaration, never from a reaction magnitude that is solver
      noise at a pinned node)

## 3. Proof

- [x] 3.1 Worked example re-derived from a public worked example of the 7-22 equation
- [x] 3.2 A docs page for equipment anchorage: which coefficients are the user's
