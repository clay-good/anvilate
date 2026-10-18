# Tasks: Purchased components

Depends on `add-product-structure`, `add-interface-contracts`, and the STEP reader from
`add-agent-context-intake`.

## 1. Record

- [x] 1.1 Component record schema: identity, supplier numbers, envelope, interfaces,
      ratings, provenance per value
- [x] 1.2 Vendor STEP by path and SHA-256; hash mismatch makes geometry not evaluated
- [x] 1.3 Draft records from a measured vendor STEP; confirmation before use

## 2. Families

- [ ] 2.1 Dimension tables with provenance for motor frames, deep-groove ball bearings,
      profile rail size classes, couplings, fan frames — dimension data only, never a
      redistributed catalog
- [ ] 2.2 Family generators producing records; refusals with nearest designations

## 3. Ratings

- [x] 3.1 Rating-to-quantity map per family
- [x] 3.2 Bearing basic rating life (cited life equation), motor torque margin, guide
      stroke and load, gas spring force — each a card entry
- [x] 3.3 Not evaluated when the product does not supply the quantity

## 4. Sourcing

- [x] 4.1 Unsourced marking; release export blocked on unsourced components
- [ ] 4.2 A docs page for components: writing a record, citing a datasheet, using a vendor model
