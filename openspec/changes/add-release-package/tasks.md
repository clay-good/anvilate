# Tasks: Release package

Depends on `add-product-structure`, `add-purchased-components`, `add-product-screening`.

## 1. Gate

- [ ] 1.1 Release refusal naming every blocking path (failing card, placeholder,
      unsourced, provisional number); draft marking in all file metadata and drawings
      (the refusal and the STEP and manifest marking are built; drawings are not)

## 2. STEP

- [ ] 2.1 XCAF writer: hierarchy, product names = part numbers, unique instance names
      from paths, color per part, user-defined attributes, validation properties
- [x] 2.2 Per-part files `<pn>_<rev>.step`; optional external-reference assembly
- [ ] 2.3 Import matrix in CI on the free CAD tiers: tree depth, names, colors survive

## 3. BOM

- [x] 3.1 Indented BOM CSV and XLSX with the field list; find numbers shared with
      drawings
- [x] 3.2 Column profiles; profile schema; refusal of unknown fields
- [x] 3.3 Buy list summed across instances and exported variants

## 4. Routed outputs

- [x] 4.1 Profile-cut DXFs to shop conventions with cut list
- [x] 4.2 3MF print plate with quantities
- [x] 4.3 Machined parts: STEP and part drawing
- [x] 4.4 Driving-parameter CSVs, one column per variant

## 5. Drawings and manifest

- [ ] 5.1 Assembly drawing per product node: views, exploded view, balloons, parts list
- [ ] 5.2 One PDF package
- [x] 5.3 Manifest with hashes; `anvilate verify` reports altered files
- [ ] 5.4 A docs page for the release package: what lands where and which tool reads it
