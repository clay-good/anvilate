# Change: Release package — hand a product to the tools and people that build it

## Why

Anvilate is not a CAD system and will not become one. Its value ends at the handoff, so
the handoff has to be good enough that nobody retypes anything. For a single part, a STEP
file and a sheet are enough. For a product, the engineer's next hour goes to work the
tool could have done:

- Opening a STEP assembly and finding `Imported1`, `Imported2`, a flattened tree, or
  duplicate names that their CAD silently substituted.
- Rebuilding the BOM by hand in the column layout their PLM or ERP import expects.
- Splitting the parts by who makes them: one DXF per laser-cut part for the sheet-metal
  shop, a print plate for the 3D printer, STEP and a drawing for the machine shop, a buy
  list for purchasing.
- Producing an assembly drawing whose balloons match the parts list.

Each of these has a known, boring, correct form, and engineers' CAD, PDM, PLM, ERP and
shops all accept that form. This change emits it.

## What Changes

| Area | Change |
| --- | --- |
| STEP assembly | One AP242 file by default, with the real hierarchy, product names equal to part numbers, unique instance names, color per part, and properties (part number, revision, material, mass, make/buy) as user-defined attributes. Per-part STEP files named `<part number>_<rev>.step` beside it for replace-component workflows and PLM attachment. |
| BOM | Indented BOM as CSV and XLSX with level, find number, parent part number, and the fields purchasing and planning need; a flat buy list summed across the tree; user-supplied column profiles that map the BOM onto a PLM or ERP import template. |
| Routed by process | A folder per process: laser and waterjet DXFs to shop conventions with a cut list, a 3MF print plate with quantities, machined parts with STEP and drawing, purchased parts with the buy list. |
| Drawings | An assembly drawing with balloons whose numbers are the BOM's find numbers, a parts list, and an exploded view; part drawings as today. One PDF package. |
| Driving parameters | A CSV of each item's driving parameters in design-table shape, for engineers who rebuild or link in native CAD. |
| Manifest | A manifest listing every file with its SHA-256, the product revision, and the card verdict it was gated on. |
| Release gate | A release is refused while the card fails, while any item is a placeholder or unsourced, or while any part number is provisional. A draft export is always available and marked draft in every file. |

## Impact

- New capability: `release-package`. Deltas: `artifact-export` (ADDED),
  `drawing-generation` (ADDED).
- Builds on `add-product-structure` (identity, tree), `add-purchased-components`
  (sourcing), `add-product-screening` (the card it gates on). Reuses existing STEP, DXF
  and 3MF writers and the evidence bundle.
- Explicitly out: native CAD files of any vendor; formats needing commercial toolkits
  (JT, Parasolid, native DWG beyond the existing optional converter); pushing anything to
  a PLM, ERP or shop (files only; the user uploads them); STEP external-reference sets as
  the default (offered, because moved or partial sets import as empty components).
