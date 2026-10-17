# Industry depth: what aerospace, automotive, medical and machinery engineers need

Research on 2026-10-17 into how engineers in each industry work day to day, and what
Anvilate already covers (about 260 closed-form modules, wide but shallow on lightweight
structures and on quality records). No tools are named. Standards are named because they
are what engineers cite.

## What each industry hands in

| Industry | The deliverable reviewers read | Where Anvilate falls short today |
| --- | --- | --- |
| Spaceflight and aircraft | A margin table. Each row has the failure mode, the governing load case, an allowable with its A or B basis, the factor of safety and fitting factor, and a margin of safety for yield and ultimate. A free body backs each row. | Results are a safety factor and a utilization. Loads are not tagged limit or ultimate, there are no factor sets, and nothing envelopes hundreds of load cases |
| Automotive and Tier 1 | DFMEA → special characteristics → DVP&R → control plan, plus material-data and substance declarations | A failure-mode catalog and a verification plan, without those forms' structure |
| Medical devices | A trace from requirement to verification, a risk file, and biocompatibility and sterilization basis | Requirement-to-check traceability exists. There is no risk structure and no material attributes |
| Industrial machinery | A risk assessment, guarding, and machine-element ratings. The EU Machinery Regulation applies from 2027-01-20 | Machine elements are strong. There is no risk structure |

## Methods worth adding, by public anchor

| Method | Public-domain or open anchor |
| --- | --- |
| Margin of safety, factor sets by verification approach | NASA-STD-5001B; GSFC-STD-7000B; 14 CFR 25.303 and 25.625 |
| Preloaded joints: preload scatter, separation, slip | NASA-STD-5020B, revalidated January 2026 |
| Lugs with transverse and oblique loads | The Air Force stress analysis manual (AFFDL-TR-69-42) |
| Crippling, plastic buckling, cylinder knockdown | NASA TM X-73305; NASA-SP-8007 |
| Random vibration (Miles' equation, 3σ) | GSFC-STD-7000B and NASA practice |
| Laminates (ABD matrix, first-ply failure) and sandwich panels | Classical lamination theory; NASA TM X-73305 |
| Cycle counting over duty cycles | ASTM E1049 rainflow, then Miner's rule |
| Outgassing screen | ASTM E595 limits |
| Galvanic compatibility | Public-release military data |

## Licensing tripwires (the doctrine already in `openspec/project.md`, extended)

The following are cited, never bundled. Their values are entered by the user with a
citation:

- the aerospace allowables handbook that succeeded MIL-HDBK-5;
- the paid composites and design-data handbooks;
- the automotive quality-core handbooks, including their FMEA rating tables and
  action-priority matrix;
- the paid bolted-joint guideline's tables;
- O-ring housing standards;
- guarding-distance standards.

Commercially restricted substance lists are fetched with the user's consent. Copyrighted
textbooks' equations may be cited, but their design curves are never digitized.

## The changes this produced

| Change | One line |
| --- | --- |
| `add-industry-profiles` | One declaration sets factors, mandatory checks, records and drawing standard for an industry or company |
| `add-margin-of-safety-reporting` | Limit and ultimate loads, cited factor sets, allowable basis, a governing case per check, the margin table, free bodies |
| `add-structural-hand-methods` | Preloaded joints to NASA-STD-5020B, lugs, crippling, fastener groups, laminates, sandwich panels, random vibration, a fracture-control helper |
| `add-durability-and-sealing` | Duty cycles with rainflow counting, joint embedding loss, seals across temperature and pressure, plastic creep, modal separation, drop |
| `add-geometric-dfm-rules` | Shop-quote rules measured on the built solid for six processes, plus tooling-aware cost |
| `add-quality-artifacts` | DFMEA, special characteristics, DVP&R, control-plan seed, stable characteristic numbers, risk records, ReqIF traceability |
| `add-material-compliance` | Polymers, elastomers and composite lamina, substance screening, composition export, recycled content, material needs, galvanic pairs |
| `add-cae-handoff` | Analysis-ready decks for the user's solver, with interface loads read back into the hand methods |

The existing `add-product-screening` gained mass maturity and growth allowance, which
aircraft and automotive programs both track.

## Order

1. Margin reporting and structural hand methods. They make aerospace reviewers able to
   use the output at all.
2. CAE handoff. It fits Anvilate into the solver workflow those programs already run.
3. DFM rules and durability. These are the highest-volume value for automotive and
   consumer products.
4. Quality artifacts and material compliance, which need product structure first.
5. Industry profiles, last, because they configure everything above.
