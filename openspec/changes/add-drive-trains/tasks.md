# Tasks: Drive trains

Depends on `add-product-structure`. Uses `add-interface-contracts` and
`add-purchased-components` when present; works with declared items without them.

## 1. Declaration and flow

- [x] 1.1 Drive-train schema on product documents: shafts, carried items, meshes, input,
      required output and life
      (`Product.drive_train` at document schema 1.17.0; every shaft and gear names one of the
      product's own instances, the flow is derived at parse, and `product_screening` puts the
      output-speed and shaft-bending entries on the product's card)
- [x] 1.2 Speed, torque and power flow with cited efficiencies; output band check
- [x] 1.3 Speed-graph consistency: single determination, center distance closure,
      reverted layouts, one input, no undriven shaft
- [ ] 1.4 Refusal of typed mesh torques inside a declared train
      (`check_typed_torque`; the mesh screen does not call it until the train is a product
      field)

## 2. Meshes

- [ ] 2.1 Read ISO 21771-1:2024 and anchor contact ratio, undercut, tip thickness,
      center distance and backlash to it ("anchor before implementing")
- [ ] 2.2 Validity-range guards from ISO 6336-1:2019 on every rating screen
- [ ] 2.3 Decide the rating basis per screen (existing AGMA-form screen, ISO 6336, ANSI/AGMA
      2101-E25) and record each edition read; no edition from memory

## 3. Shafts and bearings

- [ ] 3.1 Mesh forces (tangential, radial, axial) applied at gear stations
      (tangential and radial applied at declared stations by `solve_shaft_statics`, resolved
      with each mesh's declared `line_of_centers`; axial waits on helical gears)
- [x] 3.2 Two-bearing statics; indeterminate shafts named; declared splits with basis
- [x] 3.3 Existing shaft, key and bearing screens fed derived loads as dependent entries
      (`bearing_demands` sources each bearing's equivalent load, speed and required life to
      the derivation it came from; the shaft and key screens take the flow's torque and the
      statics' peak moment directly)
- [x] 3.4 Deflection and slope at gears and bearings; limits declared or from a cited table
      (`solve_shaft_curve` reads the elastic curve at every bearing and station;
      `screen_shaft_curve` holds each against the limit declared on it with its source. No
      table is bundled: a cited one waits on reading it, and a declared limit is enough)

## 4. Heat, motion, data

- [ ] 4.1 Read ISO/TR 14179-1 (or AGMA 947-A23) and anchor the heat balance; until then
      the entry is not evaluated naming it
- [ ] 4.2 Envelopes of revolution; swept clearance to stationary items and across shafts
- [ ] 4.3 Gear data block on drawings and in the release package
- [ ] 4.4 Shigley power transmission case study as a golden test, re-derived from the
      chapter's published values
      (speeds, torques and tangential loads held, 10th ed. Ch. 18; shafts and bearings
      follow with 3.x)
- [ ] 4.5 The gear reducer worked product declares its drive train; docs page for drive
      trains
