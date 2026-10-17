# Change: Product change control — every change says what it touches, and fits into what already exists

## Why

Most mechanical design is not a blank page. It is a change to a product that already
exists: a longer stroke, a cheaper motor, a bracket that cracked in the field. Two things
make a change safe, and engineers do both by hand today.

- **Knowing what it touches.** A bore that grows 1 mm changes the bearing, the shaft, the
  housing drawing, the BOM, the buy list and every product that uses the housing. The
  engineer must decide whether the changed part is still interchangeable with stock on the
  shelf (a new revision) or not (a new part number). That decision is written up as an
  engineering change order, and the evidence is assembled by hand.
- **Designing against what is already built.** The new part has to fit the machine on the
  floor, which exists as a STEP assembly from the user's CAD, not as an Anvilate document.

Text-first design has an advantage here that GUI CAD lacks: the product is a document, so
a change is a diff. This change turns that diff into the record an engineer and their PLM
need, and lets an existing assembly be the fixed context a new item is designed against.

## What Changes

| Area | Change |
| --- | --- |
| Product diff | Two revisions of a product are compared item by item: added, removed, changed, with each change classified as affecting form, fit or function by what it touched (geometry, an interface, a rating, a check verdict). |
| Interchangeability | A changed item whose interfaces or parent's card changed is flagged as needing a new part number; one that changed only inside its envelope is flagged for a revision. The engineer decides; the system states the evidence. |
| Where used | Every changed item lists every path that uses it in the product, and the files in the last release that it affects. |
| Change record | Each diff writes a change record (Markdown and JSON): changed items, classification, verdict changes (newly failing, newly passing), mass and cost deltas, and affected files. It seeds the user's ECO; the PLM owns the workflow. |
| Revision discipline | A release whose item content changed since the last release while its revision did not is refused, naming the item. |
| Existing assemblies as context | A STEP assembly in the context folder is read as a reference item: its tree, names, placements and envelopes. New items can be placed against it and checked for interference and clearance; it is never exported as made. |

## Impact

- New capability: `product-change-control`. Delta: `input-ingestion` (ADDED).
- Builds on `add-product-structure`, `add-interface-contracts`, `add-release-package`
  (the last release's manifest is the baseline), and `add-agent-context-intake` (the STEP
  reader). Extends `headless-automation`'s existing geometric diff from parts to products.
- Explicitly out: approval workflows, sign-off, effectivity dates and serial ranges
  (PLM's job); face-level persistent references into the user's native CAD (STEP cannot
  carry them reliably).
