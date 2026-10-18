# Release package

**The files a product is handed over as, gated on its card.** `export_package(product,
folder, release=...)` writes a product into a folder in the forms a PLM, an ERP, purchasing
and CAD already read, and a manifest that hashes every file.

```python
from anvilate.release import export_package, verify_package

export_package("examples/products/linear_stage.product.yaml", "out/stage", release=False)
verify_package("out/stage")          # () while every file matches its manifest
```

## Release or draft

A **release** is refused, naming every blocking path, while any of these hold:

| Blocker | Named as |
| --- | --- |
| the card fails | `the card fails at stage/drive[2]` |
| an item is a placeholder | `reducer/gearbox is a placeholder` |
| a component is unsourced | `stage/motor is unsourced` |
| a part number is provisional | `stage/rail has the provisional part number PROV-…` |

A **draft** is written at any time. Its manifest says `draft` and lists the blockers, and
every STEP header carries the unvalidated watermark naming them.

## What lands where

| File | What it is | Read by |
| --- | --- | --- |
| `bom.csv`, `bom.xlsx` | the indented BOM: level, find number, parent part number, part number, revision, description, quantity per parent, unit of measure, material, finish, make/buy, process, manufacturer, manufacturer part number, supplier part numbers, unit mass, files | a PLM or ERP BOM import |
| `buy.csv` | each purchased item once, its quantity summed across every instance and exported variant, with the paths that use it | purchasing |
| `step/<part number>_<revision>.step` | each catalog part, watermarked | CAD, a machine shop |
| `step/<product>.step` | the assembly, one named product per item | CAD |
| `parameters/<part number>.csv` | each item's layout parameters, one column per variant | a native CAD design table |
| `manifest.json` | the product, its revision, release or draft, the card's verdict, the blockers, and every file with its role and SHA-256 | `anvilate verify` |

The manifest also lists each item with its part number, revision, content hash,
parameters and files, which [change control](changes.md) compares against. Pass the last
release's manifest as `baseline=` and a release is refused while an item changed under the
revision it was released as. Unchanged content regenerates byte for byte.

`anvilate verify out/stage` checks every file against the manifest and reports one that is
missing or altered, by path and both hashes; it exits 1 when one is.

Not yet built: column profiles, profile-cut DXFs and a cut list, the 3MF print plate,
drawings and the PDF package, external-reference assemblies, colors and attributes in the
STEP, and the CAD import matrix.
