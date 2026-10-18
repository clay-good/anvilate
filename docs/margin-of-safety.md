# Margins of safety

**The stress report an aerospace reviewer expects: one row per check, the governing load
case named, every factor in its own column.** For each check, yield and ultimate get
separate rows:

MS = allowable / (applied × FS × special factors) − 1, and a row passes at MS ≥ 0.

`anvilate.margin_of_safety` computes that table under a named, cited factor set. It refuses
the errors a reviewer looks for first:

| Error | What happens |
| --- | --- |
| A load that does not say whether it is limit or ultimate | The report is refused, naming the load case. |
| An ultimate load factored again | It is never factored again. The row shows FS 1.0 and "ultimate (not factored again)". |
| An allowable on a weaker basis than the set requires | The row is not evaluated, naming the basis required and the basis given. |
| A material the set will not qualify by analysis alone | The row is refused with the clause, and the test the set requires is added to `required_tests`, and `verification_items()` hands it to the verification plan. |
| One case reported out of hundreds | The row names the governing case, the count evaluated, every tie, and every case that could not be evaluated. |

## Binding a set and reading the table

```python
from anvilate.margin_of_safety import (
    Allowable, AllowableBasis, LoadCase, LoadLevel, LoadPath, MarginCheck, MaterialClass,
    QuantityKind, VerificationApproach, factor_set, margin_table,
)

lug = MarginCheck(
    item="bus/hinge-fitting", subsystem="bus", failure_mode="lug net tension",
    method="P / ((W - D) t)", method_citation="AFFDL-TR-69-42 §1.3",
    quantity=QuantityKind.STRESS, unit="MPa", material_class=MaterialClass.METALLIC,
    load_path=LoadPath.SINGLE, approach=VerificationApproach.TEST,
    yield_allowable=Allowable(value=414.0, basis=AllowableBasis.A, source="MMPDS-18 7075-T7351"),
    ultimate_allowable=Allowable(value=476.0, basis=AllowableBasis.A, source="MMPDS-18 7075-T7351"),
    special_factors=("fitting",),
    cases=(
        LoadCase(case="taxi bump", applied=180.0, level=LoadLevel.LIMIT),
        LoadCase(case="hard landing", applied=240.0, level=LoadLevel.LIMIT),
        LoadCase(case="crash 9g", applied=400.0, level=LoadLevel.ULTIMATE),
    ),
)
report = margin_table([lug], factor_set("14-cfr-25"))
for row in report.rows:
    print(row)
```

The ultimate row reads MS +0.03 at "crash 9g": 476 / (400 × 1.0 × 1.15) − 1. That case was
declared ultimate, so only the fitting factor applies. The hard-landing case gives
476 / (240 × 1.5 × 1.15) − 1 = +0.15. The yield row reads +0.73 at "hard landing":
414 / (240 × 1.0) − 1. The fitting factor of 25.625 is an ultimate-load factor, and the
crash case is named as one a yield margin cannot be computed on.

`report.to_csv()` and `report.to_xlsx()` write the table, and `report.section()` writes it
as a Markdown report section. Each opens with the lowest margin per subsystem, followed by
every row in ascending margin. Rows that were not evaluated come first, because a margin
nobody computed is the least known. CSV text cells that a spreadsheet would read as a
formula are prefixed with `'`. The XLSX holds only strings and numbers, never formulas.

A company's own set is a `FactorSet` with its document number as `source`. Every row
computed under it names the set and the source.

## What the bundled sets cite

Every value was read on 2026-10-17 from the document itself, not recalled.

| Set | Source read | Values |
| --- | --- | --- |
| `nasa-std-5001b-prototype` | [NASA-STD-5001B w/Change 3](https://standards.nasa.gov/standard/NASA/NASA-STD-5001), 2022-10-24 | Metallic 1.0 yield / 1.4 ultimate (Table 1). Composite 1.4, and 2.0 at discontinuities (Table 2). Beryllium 1.4 / 1.6 (Table 7). Glass and ceramics 3.0 (Table 3). |
| `nasa-std-5001b-protoflight` | the same | Metallic 1.25 / 1.4. Composite 1.5, and 2.0 at discontinuities. Beryllium and glass as above. |
| `gsfc-std-7000b-static` | [GSFC-STD-7000B](https://standards.nasa.gov/standard/GSFC/GSFC-STD-7000), 2021-04-28, extended 2026-04-24 | Table 2.2-3, static and sine loads. Metallic 1.25 / 1.4. Beryllium 1.4 / 1.6. Composite, and bonded inserts and joints, 1.5. Metallic analysis-only 2.0 / 2.6 (§2.4.1.3). |
| `gsfc-std-7000b-random` | the same | Table 2.2-3, random and acoustic loads. Metallic 1.6 / 1.8. Beryllium 1.8 / 2.0. Composite and bonded 1.9. |
| `14-cfr-25` | [14 CFR Part 25](https://www.ecfr.gov/current/title-14/chapter-I/subchapter-C/part-25), eCFR current 2026-10-15 | 1.5 ultimate (25.303). Yield at limit load (25.305(a)). Fitting factor 1.15 (25.625(a)). Casting factors 1.25 to 2.0 (25.621(c), (d)). The highest special factor governs (25.619). A-basis for a single load path and B-basis for redundant structure (25.613(b)). |

Exclusions from analysis-only qualification:

- GSFC-STD-7000B §2.4.1.3 excludes composite, beryllium and bonded structure.
- NASA-STD-5001B §4.1.2.3 allows analysis-only verification for metallic structure only.

What the sources do not state is left out rather than filled in:

- NASA-STD-5001B gives no numeric analysis-only factors for metallic structure. FSR 16
  leaves them to the project, so that combination reports "states no factors".
- NASA-STD-5001B does not cover fitting factors (§1.2.1).
- GEVS's own note 3 cross-references §2.4.1.1.1, but the analysis-only factors are in
  §2.4.1.3, so that is the clause cited.
- Paid standards' factors (the MMPDS allowables, the composites handbooks) are cited,
  never bundled. Enter them in your own set with their source.

## Free bodies

A check can carry a `FreeBody` per load case: the item's outline, the applied loads, and
the reactions at each connection. The governing row carries the free body of its governing
case. If the residual exceeds the body's tolerance, the row gets a `finding`. The default
tolerance is 1% of the largest applied load for ΣF, and that force times the outline's
diagonal for ΣM. The finding does not change the row's verdict: it says the reactions
shown are not the ones the loads produce. `FreeBody.svg()` draws it with applied loads
solid and reactions dashed, and `anvilate.raster.svg_to_png` turns it into a PNG.

Not yet built: loads read from a solver deck (`add-cae-handoff`).
