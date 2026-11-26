# Tasks: Eurocode 3 steel pack

Depends on `add-standards-effectivity` (design basis and edition) and
`expand-open-design-data` (European profile geometry). Reuses the structural pack in
`src/anvilate/packs/structural.py` where limit states are shared.

## 1. Basis and data

- [ ] 1.1 Read EN 1993-1-1:2005+A1:2014 and EN 1993-1-1:2022; record each clause the pack
      cites with its edition ("anchor before implementing")
      (the 2005+A1:2014 generation is read, from the European Commission JRC report that
      reproduces Table 5.2 with its clause numbers; see design.md. **EN 1993-1-1:2022 could
      not be read from here**, so nothing claims to answer it and 2.5 waits with it)
- [ ] 1.2 Nationally determined parameters as typed inputs with bundled recommended values
      and cited user override
- [ ] 1.3 Steel grade records S235 to S460 by thickness range, cited to the product standard
- [ ] 1.4 European profiles through the open-geometry importer; properties computed

## 2. Members (EN 1993-1-1)

- [x] 2.1 Cross-section classification
      (`anvilate.analysis.en1993_classification`: Table 5.2 in full — internal parts,
      outstand flanges, angles and tubular sections, the combined branches on α and ψ, and
      a rolled I-section's web and flange under clause 5.5.2(6). α, ψ and k_σ are refused
      rather than defaulted, and an outstand has no bending-only column because the table
      gives it none. Anchored on the report's two worked classifications down to their
      intermediate ratios)
- [x] 2.2 Cross-section resistance: tension, compression, bending, shear, interactions
      (`anvilate.analysis.en1993_resistance`: §6.2.3 to §6.2.6 plus the §6.2.8 shear
      reduction, §6.2.9.1's axial reduction with its a ≤ 0,5 cap and §6.2.9's biaxial sum.
      Partial factors are arguments with no default until 1.2 types them. Anchored on four
      published results, with the source's own Eq. (1.27) typo recorded and recovered from
      its Eq. (1.28). §6.2.9.1(4)'s second condition is not implemented: the source does not
      state it)
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
