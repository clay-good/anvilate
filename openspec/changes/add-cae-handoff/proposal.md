# Change: CAE handoff — feed the analyst's solver, and read its answers back into the hand calcs

## Why

In aerospace and automotive programs, Anvilate will not be the only analysis tool, and
it should not try to be. Engineers already run commercial or open FE solvers. What sits
between that solver and a signed stress report is slow, error-prone manual work:

- **Into the solver.** Somebody rebuilds the loads, supports, materials and load cases
  the design spec already states, by hand, in the solver's input format.
- **Out of the solver.** Somebody pulls interface loads out of the result file (grid-point
  forces at a joint, a free body cut through a fitting) and types them into a
  spreadsheet of hand calculations: lug, bolt group, crippling, joint separation. Large
  programs do this for hundreds or thousands of load cases. Commercial tools sell exactly
  this bridge.

Anvilate's spec already holds everything the first step needs. Its cited hand methods are
everything the second step feeds. Two open, text-based solver input formats cover most
of the market: the keyword format and the bulk-data format. Open
libraries already parse their result files.

This change makes Anvilate the layer on either side of the user's solver. It is not a
replacement for it.

## What Changes

| Area | Change |
| --- | --- |
| Deck export | A built part or product exports as an analysis-ready input deck (keyword `.inp` or bulk-data `.bdf`): mesh, materials, sections, the declared supports and loads by tagged face, and one step or subcase per load case. The units system is stated in the deck and in a sidecar. |
| Honest decks | A deck is marked as input, not evidence. Anvilate never presents a result it did not compute as passing one of its checks unless the result is read back through the import below. |
| Interface-load import | Grid-point or free-body forces at named interfaces are read from result files, per load case, with the file hash, case identity and coordinate system. They become load cases on the product's connections. |
| Hand calcs on solver loads | Every connection and part screen can run on imported loads. With many load cases, each screen reports its governing case (see `add-margin-of-safety-reporting`). |
| Result spot reads | Peak stress or displacement in a tagged region can be read from a result file as a cited input to a check, never as a silent replacement for one. |

## Impact

- New capability: `cae-interop`. Delta: `analysis-library` (ADDED).
- Builds on `add-product-structure` (tagged interfaces and connections), the existing
  member-force ingestion doctrine ("No silent conventions on imported analysis data"),
  and the meshing pipeline and deck writer specified in `add-local-fea`, which this change
  reuses rather than duplicates: the deck Anvilate solves itself and the deck it hands the
  analyst come from one writer. Optional dependencies (result-file readers) are
  isolated like the existing optional extras.
- Explicitly out:
  - Running commercial solvers.
  - Crash and explicit dynamics decks.
  - Proprietary binary result formats without an open reader.
  - Composite ply definitions in decks. These come after laminate screening exists.
