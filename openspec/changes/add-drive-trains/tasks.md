# Tasks: Drive trains

Depends on `add-product-structure`. Uses `add-interface-contracts` and
`add-purchased-components` when present; works with declared items without them.

## 1. Declaration and flow

- [ ] 1.1 Drive-train schema on product documents: shafts, carried items, meshes, input,
      required output and life
- [ ] 1.2 Speed, torque and power flow with cited efficiencies; output band check
- [ ] 1.3 Speed-graph consistency: single determination, center distance closure,
      reverted layouts, one input, no undriven shaft
- [ ] 1.4 Refusal of typed mesh torques inside a declared train

## 2. Meshes

- [ ] 2.1 Read ISO 21771-1:2024 and anchor contact ratio, undercut, tip thickness,
      center distance and backlash to it ("anchor before implementing")
- [ ] 2.2 Validity-range guards from ISO 6336-1:2019 on every rating screen
- [ ] 2.3 Decide the rating basis per screen (existing AGMA-form screen, ISO 6336, ANSI/AGMA
      2101-E25) and record each edition read; no edition from memory

## 3. Shafts and bearings

- [ ] 3.1 Mesh forces (tangential, radial, axial) applied at gear stations
- [ ] 3.2 Two-bearing statics; indeterminate shafts named; declared splits with basis
- [ ] 3.3 Existing shaft, key and bearing screens fed derived loads as dependent entries
- [ ] 3.4 Deflection and slope at gears and bearings; limits declared or from a cited table

## 4. Heat, motion, data

- [ ] 4.1 Read ISO/TR 14179-1 (or AGMA 947-A23) and anchor the heat balance; until then
      the entry is not evaluated naming it
- [ ] 4.2 Envelopes of revolution; swept clearance to stationary items and across shafts
- [ ] 4.3 Gear data block on drawings and in the release package
- [ ] 4.4 Shigley power transmission case study as a golden test, re-derived from the
      chapter's published values
- [ ] 4.5 The gear reducer worked product declares its drive train; docs page for drive
      trains
