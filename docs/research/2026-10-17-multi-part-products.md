# From parts to products: patterns worth borrowing

Research done on 2026-10-17 across code-CAD libraries, agent-driven CAD tools, CAD MCP
servers, electronics design automation, knowledge-based engineering, PLM/ERP import
practice, open-hardware documentation tools, and engineering trust surveys. Tools are not
named here on purpose. The point is the patterns, and where each one lands in Anvilate's
spec set.

## What engineers told the market

| Pain point (forums, reviews, surveys) | What it rules in or out for Anvilate |
| --- | --- |
| Agent-made assemblies are unstable, and fits and interfaces are where AI CAD breaks down | Interfaces must be typed and checked. A placed picture is not proof of fit |
| Invented standards, such as a motor frame size that does not exist | Purchased parts come from tables or cited records, never from memory |
| Checking a render proves neither fit nor function | Every product-level claim is a cited entry on the card |
| Imported STEP assemblies come in flattened, renamed `Imported1`, or with colliding names | The STEP writer owns names, hierarchy and uniqueness |
| Top-down parameters do not flow into assemblies, and in-context references break | Shared parameters are named values that items read. They are never geometric references between parts |
| Engineers trust AI least for verification (16%) and part selection (13%), and 61% say explainability would build trust | Deterministic, cited checks with the agent kept at the edge. This is the existing doctrine, carried to products |

## Patterns, and where each one lands

| Pattern | Where it is proven | Anvilate change |
| --- | --- | --- |
| Reusable definitions placed as instances, nested to any depth | Hierarchical schematics, CAD sub-assemblies, PLM engineering BOMs | `add-product-structure` |
| Skeleton or layout model: shared datums and driving parameters, kept out of the BOM | Top-down CAD practice, rule-driven configurators | `add-product-structure` (layout) |
| Ground one item, then place every other item along a deterministic chain rather than through a general solver | Code-CAD joint APIs, open assembly workbenches | `add-product-structure` (reuses combination mates) |
| Placeholders first, detail later, with every conclusion marked provisional | Envelope-first layout practice, systems-engineering mass-budget practice | `add-product-structure` |
| Lazy, dependency-tracked regeneration | Knowledge-based engineering frameworks | `add-product-structure` (content-keyed rebuild) |
| Named, typed interface frames on parts. The agent names interfaces and never writes coordinates | Code-CAD anchors and joints, mate connectors | `add-interface-contracts` |
| A connection list separate from placement | Electronics netlists | `add-interface-contracts` |
| A compatibility table between interface kinds | Electrical rule check pin matrices, joint pairing tables | `add-interface-contracts` |
| Checks that ship with the interface or component | Electronics code-first design tools | `add-interface-contracts`, `add-purchased-components` |
| "Unconnected" and "deliberately open" markers | Electrical rule check and no-connect flags | `add-interface-contracts` |
| Interface control document as a generated artifact | Aerospace systems-engineering practice | `add-interface-contracts` |
| Component record = connections + space taken + 3D model + ratings + manufacturer part number | Electronics component libraries | `add-purchased-components` |
| Vendor models referenced, never redistributed | Supplier CAD terms, which offer no scripted access | `add-purchased-components` |
| Load path to ground, mass and center-of-mass roll-up, clearance, mobility count, coefficient-of-thermal-expansion (CTE) mismatch, part-count questions | Design-review checklists and design-for-assembly (DFA) methods | `add-product-screening` |
| Indented BOM with level and parent columns, a flat buy list | PLM and ERP import templates | `add-release-package` |
| One file per part for each shop, following its conventions | Profile-cutting shop file checklists, 3MF build plates | `add-release-package` |
| Stable file names so "replace component" and reload work | Live-linked neutral-file workflows in mainstream CAD | `add-release-package` |
| A design table of driving parameters | Configuration tables in mainstream CAD | `add-release-package` |
| Every change classified by form, fit and function, with where-used | Change-order practice, revision-versus-new-part-number rules | `add-product-change-control` |
| An existing assembly as fixed context | Brownfield design practice | `add-product-change-control` |
| A staged verification cascade: it builds, the geometry is valid, then intent, fit and assembly | Text-to-CAD benchmarks | Already the gauntlet's shape. Products add the assembly stage |

## Deliberately not borrowed

| Not borrowed | Why |
| --- | --- |
| A general numerical constraint solver | It can fail to converge, it can return a non-unique answer, and its failures are opaque |
| An interactive editor or viewer | That is the user's CAD (design decision D5) |
| Formats that need commercial toolkits | Native CAD already writes them |
| A scored DFA index | Its time tables are proprietary. Merge candidates are reported instead |
| A system-model language as the internal schema | Its open tooling is still settling. It can come later as an export target |

## Order

1. `add-product-structure`
2. `add-interface-contracts`
3. `add-purchased-components`
4. `add-product-screening`
5. `add-release-package`
6. `add-product-change-control`

Each change depends only on the changes listed before it, so each one ships something
usable on its own: products build and check after step 1, and they hand off cleanly after
step 5.
