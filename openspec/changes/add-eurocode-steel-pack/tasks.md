# Tasks: Eurocode 3 steel pack

Depends on `add-standards-effectivity` (design basis and edition) and
`expand-open-design-data` (European profile geometry). Reuses the structural pack in
`src/anvilate/packs/structural.py` where limit states are shared.

## 1. Basis and data

- [ ] 1.1 Read EN 1993-1-1:2005+A1:2014 and EN 1993-1-1:2022; record each clause the pack
      cites with its edition ("anchor before implementing")
- [ ] 1.2 Nationally determined parameters as typed inputs with bundled recommended values
      and cited user override
- [ ] 1.3 Steel grade records S235 to S460 by thickness range, cited to the product standard
- [ ] 1.4 European profiles through the open-geometry importer; properties computed

## 2. Members (EN 1993-1-1)

- [ ] 2.1 Cross-section classification
- [ ] 2.2 Cross-section resistance: tension, compression, bending, shear, interactions
- [ ] 2.3 Flexural buckling by the cited curves; lateral-torsional buckling
- [ ] 2.4 Bending and axial interaction by the declared method
- [ ] 2.5 Edition differences registered where the two generations diverge

## 3. Joints (EN 1993-1-8)

- [ ] 3.1 Read EN 1993-1-8:2005 and EN 1993-1-8:2024; record clauses and editions
- [ ] 3.2 Bolted connections by category; slip resistance from a declared slip factor
- [ ] 3.3 Fillet welds by the directional and simplified methods, declared

## 4. Proof

- [ ] 4.1 Golden tests from published worked examples, re-derived, per edition
- [ ] 4.2 Shared limit states registered once with both code implementations
- [ ] 4.3 Sample specs: a base plate, a gusset and a beam under a Eurocode design basis
- [ ] 4.4 A docs page for the Eurocode 3 pack: declaring the design basis and the annex
