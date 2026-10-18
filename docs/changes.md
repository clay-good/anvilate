# Changes

**What a change to a product touches, with its evidence, in the form a change order
takes.** `compare_products(before, after)` compares two revisions item by item, sub-products
included, and returns a change record.

```python
from anvilate.changes import compare_products

record = compare_products(before, after, library_before=..., library_after=...,
                          reason="customer bearing upgrade, ECR-114")
print(record.to_markdown())        # or record.model_dump_json()
```

## What is compared

Items are matched by definition id; an item in a sub-product is named `drive/bracket`.
Each is added, removed, unchanged or changed, and a changed one says what changed:

| Change | Read from |
| --- | --- |
| parameters | the spec's `element_params`, the placeholder's or component's fields, path by path |
| geometry | the built item's volume and envelope |
| interfaces | each interface as built: kind, face or axis, parameters, and the positions of its holes |
| ratings | a component's ratings |
| identity | part number, revision, description, source |
| verdicts | every entry on the item's card, and on its parent's connections that name it |

## Form, fit and function

| Class | When | Flag |
| --- | --- | --- |
| `fit` | one of its published interfaces changed | `new_part_number` |
| `function` | a rating changed, or a verdict on it or on a connection naming it | `new_part_number` |
| `form` | only its geometry or other parameters changed | `new_revision` |

The flag states its evidence (`interface bearing_bore`) and never changes the identity
itself: that is the engineer's decision, made with the evidence in front of them.

## Where it is used

Each changed item lists every instance path that uses it, pattern members each, across the
product and its variants: a bracket in four drive modules lists four paths.

## The record

`record.to_markdown()` is the change record: the two revisions, each changed item with its
class, flag, changes, evidence and paths, the unchanged items, checks newly failing and
newly passing, and the mass before and after. `reason` is yours to supply; a record without
one says **reason missing** rather than leaving it blank. The JSON is the model's dump.

## Against the last release

A release's `manifest.json` records each item's part number, revision, content hash,
parameters, and the package files that contain or reference it. Two uses:

- `compare_to_release(product, read_manifest(folder))` compares a working product with that
  release: each item added, removed, unchanged or changed, its changed parameters named,
  and an item changed under the part number and revision it was released as says so.
- `compare_products(released, working, baseline=manifest)` classifies as above, and each
  changed item lists `affected_files`: the release's per-part STEP, the assembly STEP, the
  BOM and the buy list it appears in.

A release exported with `baseline=` is refused while an item's content changed under its
released revision, naming it and what changed:
`plate (100-1) changed under revision B: element_params.holes[0].x.magnitude 0.0 → 5.0`.
Exporting unchanged content again writes byte-identical files, which CI holds.

Not yet built: cost deltas, and reading an existing STEP assembly as a reference item.
