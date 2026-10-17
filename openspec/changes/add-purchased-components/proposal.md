# Change: Purchased components — the parts you buy are checked as hard as the parts you make

## Why

In a typical machine, more than half the line items on the BOM are bought: motors,
bearings, linear guides, gas springs, couplings, casters, connectors, boards. Anvilate
draws none of them, and it should not try to. But the product is wrong if the motor's
flange does not match, if the bearing is rated below the load the shaft puts on it, or if
the rail is shorter than the stroke. Today an agent can only represent a bought part as
an anonymous envelope, so none of that is checked, and an agent asked for "a NEMA 23
motor" will write dimensions from memory. That is the hallucination engineers complain
about most in AI design tools.

Electronics libraries settled this long ago: a component is a record with its symbol
(what it connects to), its footprint (the space it takes), its 3D model, its ratings, and
its manufacturer part number, and nobody draws a resistor from memory. Mechanical
engineering has the same need and no open, typed equivalent.

## What Changes

| Area | Change |
| --- | --- |
| Component record | A purchased component is a typed record: identity (manufacturer, manufacturer part number, supplier part numbers), an envelope, its interfaces, its ratings, and the provenance of every value. |
| Families | Records for common families (stepper and servo motors by frame, ball bearings, linear guides, shaft couplings, gas springs, casters, standard fans) generated from bundled dimension tables, so `NEMA23 frame` resolves to tabulated dimensions, never recalled ones. |
| The user's own records | An engineer can write a record for a component in their catalog, with each value cited to the datasheet page it came from; the context intake reads the vendor's STEP for its envelope. |
| Vendor models are referenced, never redistributed | A vendor STEP is used from the user's folder by path and hash. It is never copied into Anvilate's data or its published examples. |
| Ratings are checked | A component's ratings are compared with what the product asks of it: a bearing's dynamic rating against the load and life, a motor's torque against the load, a rail's stroke and load rating, a gas spring's force. Each is a cited entry on the card. |
| BOM-ready | Every component carries what a buyer needs: manufacturer, part number, suppliers, unit of measure. |

## Impact

- New capability: `component-library`. Delta: `input-ingestion` (ADDED).
- Builds on `add-product-structure` (components are items) and `add-interface-contracts`
  (a record publishes interfaces). Uses `add-agent-context-intake` to measure a vendor
  STEP the user supplies.
- Explicitly out: fetching vendor CAD or prices from any website (no scripted access is
  offered, and fetching would break the local-only rule); supplier stock or lead time;
  selecting the "best" component (the agent proposes, the card checks).
