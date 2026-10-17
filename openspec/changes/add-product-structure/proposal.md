# Change: Product structure — a product is a tree of assemblies, not one long combination

## Why

A combination places a handful of catalog parts by the features they share. That covers
"bolt this bracket to that plate". It does not cover what an engineer builds next: a
linear stage, a gearbox, an enclosure with a board and a fan, a cart. Those are products,
and a product has a shape a flat list of parts cannot hold:

- **It nests.** A drive module is built, checked and bought as one thing, then placed four
  times in the product. Today the agent would have to repeat every part and mate four
  times, and a change to the module would have to be made four times.
- **It contains things nobody here draws.** A motor, a bearing, a PCB, a gas spring. They
  are bought, not made, and the product is still wrong if they do not fit.
- **It is designed before it is detailed.** An engineer blocks out the product with
  envelopes and interfaces first, checks that the layout works, and details the parts
  last. A tool that needs every part fully specified before it will say anything is only
  useful at the end, when changes are expensive.
- **Every item has an identity the rest of the company uses.** A part number, a revision,
  make or buy. Without it, nothing Anvilate writes can go into a BOM, a PDM vault or a
  purchase order without retyping.

The pattern every mature design tool converges on is the same: a hierarchical product
structure whose nodes are reusable definitions placed as instances, with an identity per
definition and a placeholder allowed at any node. Electronics design tools reached it with
hierarchical sheets; mechanical CAD with sub-assemblies and skeletons; PLM with the
engineering BOM. This change gives Anvilate that structure in its own document form.

## What Changes

| Area | Change |
| --- | --- |
| Product document | A new document kind: a product names its items (parts, combinations, sub-products, purchased components, placeholders) and places them through the same mate vocabulary a combination uses. A product may be an item in another product. |
| Definitions and instances | An item is defined once and placed any number of times. Linear and circular patterns of an instance are declared, not copied. |
| Item identity | Every definition carries an item identity: part number, revision, description, and make, buy or reference. The tree is addressable by a stable path (`frame/drive[2]/motor`). |
| Placeholders | An item may be an envelope with mass, center of mass and interfaces and no detail. Every conclusion that rests on a placeholder says so. |
| Variants | A product may declare named variants that swap an item or change a parameter, and every variant is built and checked as its own product. |
| One card per node | Each node of the tree gets its own card, rolled up to its parent, so a failing bolt inside the drive module is found at the drive module and at the product. |
| Agent surface | Products go through the existing workflow tools (build, render, export). Results are a summary tree; the agent asks for one node's detail by its path. No new tool per product concept. |

## Impact

- New capability: `product-structure`. Deltas: `spec-ir` (ADDED), `headless-automation`
  (ADDED).
- Builds on `add-part-combinations` (mates, hardware, the combination card), which stays
  the leaf assembly form. A combination is a valid product item unchanged.
- Enables `add-interface-contracts`, `add-purchased-components`, `add-product-screening`,
  `add-release-package` and `add-product-change-control`, which all address items by the
  paths and identities defined here.
- Explicitly out: an interactive assembly editor; a numerical constraint solver; flexible
  parts (cables, hoses, belts) as geometry; PLM workflow states (approval, sign-off),
  which belong to the user's PLM.
