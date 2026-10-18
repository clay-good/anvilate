# Products

**A product is a tree: definitions placed as instances, each with the identity the rest of
the company uses.** A combination places a handful of catalog parts. A product nests. A drive
module is defined once and placed twice. A motor nobody here draws is a placeholder with an
envelope and a mass. Every definition carries a part number, a revision and make or buy.

```yaml
anvilate_product: 1.0.0
name: stage
definitions:
  - id: base
    identity: {part_number: 300-0001, description: base plate, source: make}
    placeholder:
      envelope: [{magnitude: 400, unit: mm}, {magnitude: 200, unit: mm}, {magnitude: 12, unit: mm}]
      mass: {magnitude: 7.5, unit: kg}
      reason: base plate not yet detailed
  - id: drive
    identity: {part_number: 400-0001, description: drive module, source: make}
    product: drive            # another product document, from the library
  - id: foot
    identity: {description: levelling foot, source: buy}   # no number yet: provisional
    placeholder: {...}
instances:
  - {name: base, item: base}
  - {name: drive, item: drive, pattern: {kind: linear, count: 2, spacing: {magnitude: 200, unit: mm}, direction: x}}
  - {name: foot, item: foot, pattern: {kind: linear, count: 4, spacing: {magnitude: 100, unit: mm}, direction: y}}
ground: base
```

`parse_product` reads the document. `product_tree(product, library=...)` expands it, with
sub-products taken from the library by name. `parts_list(tree)` counts every item through
patterns and nesting.

## What the tree guarantees

| Rule | Why |
| --- | --- |
| Every instance has a path of names, `stage/drive[2]/motor` | A finding, a part in a list and a change record all address one occurrence, and adding or reordering a sibling does not move it. |
| A definition with no part number gets `PROV-` and eight characters of its content's hash, marked provisional everywhere | The list is complete before numbers are assigned, and nobody can mistake a provisional number for a released one. The same content always gets the same number. |
| One part number on two different items is refused, naming both paths | A part number names one item, or a purchase order buys the wrong thing. |
| A product that contains itself, at any depth, is refused | Expanding it would never end. The refusal names the chain, `a → b → a`. |
| A mirrored instance is refused | An opposite-hand part is a different part to make and to buy. Give it its own definition and number. |

Not yet built: placing instances through mates and layout datums, variants, a card per
node with roll-up, and rebuilds keyed on content.
