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
- [x] 1.2 Nationally determined parameters as typed inputs with bundled recommended values
      and cited user override
      (`NationalParameter`, `NationallyDeterminedParameter` and `NationalAnnex` in
      `en1993_resistance`; `recommended_annex()` bundles γ_M0 = 1,00, γ_M1 = 1,00,
      γ_M2 = 1,25, λ_LT,0 ≤ 0,40 and β ≥ 0,75 with the citation they were read from, and
      `national_annex` overrides any of them with a member state's, each needing its own
      clause. A γ below 1 is refused; a value outside a recommended bound is reported by
      `outside_recommendation` rather than refused, since an annex may choose outside.
      Nothing defaults to an annex: the resistances still take their factors explicitly)
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
- [x] 2.3 Flexural buckling by the cited curves; lateral-torsional buckling
      (`anvilate.analysis.en1993_buckling`: the five curves and their α, λ̄, χ, N_b,Rd, both
      lateral-torsional methods and both curve-selection tables, and the alternative
      method's second cap at 1/λ̄_LT². N_cr reuses `column.euler_buckling_load`; M_cr is
      declared because EN 1993-1-1 does not give it. Anchored on a worked column and the
      same beam worked at two critical moments)
- [x] 2.4 Bending and axial interaction by the declared method
      (`en1993_interaction`: §6.3.3's two inequalities (Eqs. 6.61 and 6.62) and Annex B
      (Method 2)'s factors for them. `InteractionMethod` is a required argument with no
      default — Annex A and Annex B are alternatives that disagree, so Method 1 refuses
      rather than answering under its own name with the other's numbers. So is
      `TorsionalSusceptibility`, which turns on restraint rather than on the section.
      k_yy's bound is a **ceiling** and k_zy's a **floor**; they coincide at a slenderness
      of 1,0. Refuses a minor-axis moment (k_yz and k_zz not carried, and dropping the term
      would make both sides smaller), classes 3 and 4, and k_zy below λ̄_z = 0,4 where
      Table B.2 branches and the source never prints it. Both of the report's worked
      beam-columns replay exactly, one on each Annex B table, and they are governed about
      **different axes** — the column about z, the hollow section about y.
      One figure of the source's does not reproduce and is recorded rather than matched:
      it prints k_zy's unbounded value as 0,966 and its floor as 0,947, where its own
      printed inputs give 0,9646 and 0,9660. The governing k_zy is 0,966 either way, so
      the example's conclusion stands; the two intermediates are asserted nowhere)
- [ ] 2.5 Edition differences registered where the two generations diverge

## 3. Joints (EN 1993-1-8)

- [ ] 3.1 Read EN 1993-1-8:2005 and EN 1993-1-8:2024; record clauses and editions
- [x] 3.2 Bolted connections by category; slip resistance from a declared slip factor
      (`en1993_bolts`: Table 3.2's five categories with the different set of checks each
      requires, both strength tables (3.1 and 3.4), shear/bearing/tension/punching with the
      asymmetric combined check, and slip resistance from a declared μ — the friction
      SURFACE's class, not the bolt's — with k_s by hole type and the 0,8 tension relief.
      `BoltCategory` has no default: a connection has no resistance until its category is
      named, and category C does not require the shear check that B does.
      Three internal contradictions in the source are recorded rather than smoothed: it
      takes α_v = 0,6 for a class 6.8 bolt where its own Table 3.4 gives 0,5 (this pack
      follows the table, so 117,6 kN against the example's 141,1); it prints α_b's
      denominator as 360 while computing with 510; and its inner-bolt k_1 differs between
      its table and its example by a factor of five, so **inner-bolt k_1 refuses** rather
      than guessing. α_b and k_1 themselves replay exactly: 0,606, 0,811 and 2,5.
      Not carried: the group-of-fasteners rule and the long-joint reduction, which need a
      bolt layout this module does not model)
- [ ] 3.3 Fillet welds by the directional and simplified methods, declared
      (**read and stopped**: Eq. 2.14's first inequality and Table 4.1's β_w are in hand,
      but the report prints `σ⊥ ≤ f_u/γ_M2` where the expected form carries 0,9, and it
      works no directional example to settle it. A 10% coefficient on a weld is not shipped
      from memory — see design.md for what a second source has to answer)

## 4. Proof

- [x] 4.1 Golden tests from published worked examples, re-derived, per edition
      (`tests/test_en1993_golden.py`: 32 published figures from the JRC report, each row
      naming its section and held to the number of decimals that section prints — the band
      is derived from the printed precision, not written down, so it cannot be widened to
      make a row pass. A meta-test exercises that. Covers all three modules, with a floor
      per module. **One edition only**: every row is the 2005 edition, because the 2022
      edition is behind 1.1's blocker — the JRC report predates it and no public document
      reproduces its clauses. The per-edition half of this task is open with 1.1.
      Also records what the corpus does *not* prove: two decimals of χ cannot resolve the
      imperfection factor to the two decimals its own table publishes, so the curve
      constants are pinned by value separately. Found by mutating the table and watching
      every worked row go on passing.)
- [ ] 4.2 Shared limit states registered once with both code implementations
- [ ] 4.3 Sample specs: a base plate, a gusset and a beam under a Eurocode design basis
- [ ] 4.4 A docs page for the Eurocode 3 pack: declaring the design basis and the annex
      (`docs/eurocode-steel.md` covers the three modules that exist — which numbers are the
      engineer's, where it refuses, and three things worth knowing before using it. The
      design-basis and annex half waits on `add-standards-effectivity` wiring and on 1.2's
      typed nationally determined parameters, so the edition is a fact the page states
      rather than something a spec declares and the pack enforces)
