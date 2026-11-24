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
- [x] 4.3 Gear data block on drawings and in the release package
      (`gear_data` at document schema 1.19.0: teeth, module, pitch diameter, pressure angle,
      profile shift, basic rack, accuracy class and the span or over-pins dimension, beside
      the mesh the gear runs in, its mating gear, the ratio and the centre distance. It is
      `gear-data.csv` in the release package and the block printed under the parts list of
      the product's own assembly sheet. A field the gear does not declare reads
      `not declared`, never a blank. Three refusals the block rests on: a mesh whose gears
      are cut to different modules, which the centre-distance check cannot see; a gear two
      meshes give two pressure angles; and a gear no mesh names. No helix angle or hand —
      the axial load one makes waits on 3.1, and a helical gear screened as a spur one is a
      wrong answer rather than a missing one. The gears are bought items with no part
      drawing of their own, so the block is on the assembly sheet)
- [x] 4.4 Shigley power transmission case study as a golden test, re-derived from the
      chapter's published values
      (10th ed. Ch. 18, the edition read off McGraw-Hill's information centre for the ISBN
      the chapter's print-marks carry rather than recalled. Speeds, torques and tangential
      loads were already held; now the countershaft is laid out from the chapter's own
      Fig. 18-2 and the whole chain — flow, mesh split, two-bearing statics, bearing
      demand — is held to the reactions Section 18-9 prints: RA = 375 lbf and RB = 1918 lbf
      with both components of each, and the 12,000 h design life as 2.8e8 revolutions. To
      two parts in a thousand, because the chapter's own Wt is printed rounded and RAz is
      the difference of two numbers an order of magnitude larger. Its force analysis
      (Ex. 7-2) and deflection check (Ex. 7-3) are in Chapter 7 and not quotable from here)
- [x] 4.5 The gear reducer worked product declares its drive train; docs page for drive
      trains
      (`examples/products/gear_reducer.product.yaml` is three shafts and four gears with a
      declared train, and `docs/drive-trains.md` is the page)
