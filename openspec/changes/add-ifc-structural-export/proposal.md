# Change: IFC export — the checked structural element goes into the building model, with its verdict attached

## Why

Anvilate's civil and structural persona ends at DXF and STEP. Their colleagues work in
BIM: the base plate, the gusset, the guardrail post and the mezzanine beam have to appear
in a building model that is exchanged as IFC, the open ISO standard for building
information (ISO 16739-1:2024 is IFC 4.3; ISO 16739-1:2018 is IFC4). A checked plate
that arrives as a STEP solid loses its identity, its material, its mass, and the fact
that it was checked. It is re-modeled by hand, and the verdict stays in a PDF nobody
links to the element.

IFC carries exactly what Anvilate knows: an element class per part (member, beam,
column, plate with a predefined type such as base plate or gusset plate, mechanical
fastener for bolts and anchors), a material association, a standard profile definition
for a rolled section so the receiving tool keeps the section rather than a lump of
faces, and property sets, standard and custom, that can hold the part number, mass,
validation status and the card digest. The open toolkit is mature: IfcOpenShell
(LGPL-3.0-or-later; 0.9.0 released 2026-10-15) writes IFC2x3 and IFC4 with full
geometry support and parses IFC 4.3, and runs in-process on the same license class as
the geometry kernel Anvilate already imports.

## What Changes

| Area | Change |
| --- | --- |
| Element export | Structural-pack elements, and products containing them, export as IFC with one element per part in the class its archetype maps to, the assembly tree as spatial or aggregation structure, part numbers as tags and names, and transforms preserved. |
| Profiles, not lumps | A member on a standard section exports with the standard profile definition and an extrusion, so the receiving tool keeps the section; a part with no standard profile exports its solid as a B-rep. |
| Properties | Standard property sets where the schema defines them (the common sets for beams, columns, members and plates) and one Anvilate property set carrying part number, revision, material, mass, validation status, the card digest and the design basis. |
| Schema | IFC4 (ISO 16739-1:2018) by default, the schema with full geometry support in the open toolkit; IFC 4.3 (ISO 16739-1:2024) as a declared option, with the capabilities the toolkit lacks for it refused by name. |
| Gated and watermarked | The export gate applies; an unvalidated export carries the watermark in the file header and in the property set. |
| Verified | Every exported file is validated against the schema with an open checker, re-read, and its element volumes and centroids compared with the built solids, as the STEP validation properties already are. |

## Impact

- Delta: `artifact-export` (ADDED). Builds on `add-release-package` (identity, tree,
  mass), `add-product-structure`, the structural, walking-working-surfaces and Eurocode
  packs, and `add-standards-effectivity` (the design basis travels in the property set).
- Optional dependency: IfcOpenShell (LGPL-3.0-or-later), in-process as an optional extra;
  the decision that LGPL is in the same class as the already-imported OCCT bindings is
  recorded in the project conventions when this lands. The core never requires it.
- Explicitly out:
  - Reading IFC (the context intake reads STEP and DXF; IFC reading is a later change).
  - The structural analysis model entities (IfcStructuralAnalysisModel) in the first
    phase; `add-frame-analysis` makes them worth a second phase.
  - Architectural, MEP or site elements; BCF issue exchange; any BIM server.
