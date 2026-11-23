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
- [x] 1.4 Refusal of typed mesh torques inside a declared train
      (`product_screening` refuses a part the train names whose typed torque, bending moment
      or pinion torque the flow or the statics contradicts, naming the derived value to
      write; `check_typed_torque` stays the standalone form for a caller screening a mesh
      directly, where leaving the torque out *is* the remedy)

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
- [x] 4.2 Envelopes of revolution; swept clearance to stationary items and across shafts
      (`DriveShaft.axis` at document schema 1.18.0; `product_screening` sweeps each carried
      item's bounding box about it and gauges every envelope against the declared
      `min_clearance`, skipping one shaft's own items, gears in mesh, and pairs a mate
      holds. The worked reducer declares no axis until its gears sit on their shafts)
- [ ] 4.3 Gear data block on drawings and in the release package
- [ ] 4.4 Shigley power transmission case study as a golden test, re-derived from the
      chapter's published values
      (speeds, torques and tangential loads held, 10th ed. Ch. 18; shafts and bearings
      follow with 3.x)
- [x] 4.5 The gear reducer worked product declares its drive train; docs page for drive
      trains
      (`examples/products/gear_reducer.product.yaml` is three shafts and four gears with a
      declared train, and `docs/drive-trains.md` is the page)
