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
every file carries the unvalidated watermark naming them: in each STEP header, each profile
DXF's header, the print plate's metadata, and at the top of each drawing sheet (and in its
`<meta name="ANVILATE_EXPORT_STATUS">`). A release's files carry `VALIDATED` in the same
places.

## What lands where

| File | What it is | Read by |
| --- | --- | --- |
| `bom.csv`, `bom.xlsx` | the indented BOM: level, find number, parent part number, part number, revision, description, quantity per parent, unit of measure, material, finish, make/buy, process, manufacturer, manufacturer part number, supplier part numbers, unit mass, files | a PLM or ERP BOM import |
| `buy.csv` | each purchased item once, its quantity summed across every instance and exported variant, with the paths that use it | purchasing |
| `bom-<profile>.csv` | the BOM again in each column profile's headers, order, level form and make/buy spellings | a template that is not the default |
| `machined/<part number>_<revision>.step`, `.html` | a machined part's STEP and its drawing sheet | the machine shop |
| `laser/<part number>_<revision>.dxf`, `laser/cut-list.csv` | a profile-cut part's flat profile at 1:1 on cut layers; the cut list of part number, material, thickness and quantity | the laser, waterjet or sheet-metal shop |
| `print/plate.3mf` | every printed part on one plate, each placed as many times as the product uses it | a slicer |
| `step/<part number>_<revision>.step` | any other part, watermarked | CAD, the shop its process names |
| `step/<product>.step` | the assembly, one named product per item, each in a color of its own, and each occurrence named by its product and its path (`R-15 rail @ rail[1]`) | CAD |
| `parameters/<part number>.csv` | each item's layout parameters, one column per variant | a native CAD design table |
| `manifest.json` | the product, its revision, release or draft, the card's verdict, the blockers, and every file with its role and SHA-256 | `anvilate verify` |

The manifest also lists each item with its part number, revision, content hash,
parameters and files, which [change control](changes.md) compares against. Pass the last
release's manifest as `baseline=` and a release is refused while an item changed under the
revision it was released as. Unchanged content regenerates byte for byte.

`anvilate verify out/stage` checks every file against the manifest and reports one that is
missing or altered, by path and both hashes; it exits 1 when one is.

Each catalog part's files go to the folder for its declared process: `fdm` and `sls` to the
print plate, `sheet_metal` to `laser/`, machining processes to `machined/`, the rest to
`step/`. A part its process's format cannot express (a laser-cut part with no flat profile)
gets its STEP in `step/` and is named, with the reason, in the manifest's `unrouted`.

A column profile maps the BOM onto your template:

```python
from anvilate.release import ColumnProfile

erp = ColumnProfile.model_validate({
    "name": "erp", "level": "dotted", "make_buy": {"make": "M", "buy": "B"},
    "columns": [{"field": "level", "header": "LVL"}, {"field": "part number", "header": "ITEM"},
                {"field": "make/buy", "header": "SRC"}, {"field": "quantity per parent", "header": "QTY"}],
})
export_package(product, "out", release=False, profiles=[erp])     # adds bom-erp.csv
```

`level: dotted` writes `1.2.1`, the find numbers down the tree. A profile naming a field the
BOM does not carry is refused, naming it.

Not yet built: assembly drawings and the PDF package, external-reference assemblies,
user-defined attributes and validation properties in the STEP, and the CAD import matrix.
