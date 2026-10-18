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

The document's schema is published as
[`product-document`](api/schemas/product-document.schema.json), and `anvilate_product: 1.0.0`
names its version. A definition's `product` is the name of a product in the library, a
sub-product embedded whole, or `{file: drive/drive.product.yaml}`, a path relative to the
document that names it. `load_product(path)` reads a document and every file it references,
at any depth, and returns the product and its library. A missing or unreadable file is
refused, naming the path and the definition that references it. So are files that come back
to themselves, and two different sub-products under one name.

`parse_product` reads one document already in memory. `product_tree(product, library=...)` expands it, with
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

## Placing it

Add `mates` in the [combination](combinations.md) vocabulary, with instance names as the
parts, and call `place_product(product, library=...)`. The ground stays at the origin.
Every other instance is placed through its mates onto one listed before it. A product
never states a coordinate, so an instance with no mate is refused. A catalog part is
built from its spec, and a placeholder is its envelope box. A sub-product is its own
placed assembly, moved as one body. Pattern members follow the first: shifted by the
spacing, or turned by the angle about the parent's axis.

The placed product lists every leaf body at its path with its box, the interference
between all of them, the mass and the centre of mass. The mass names each placeholder it
rests on, and each part whose material gives no density, so the roll-up never reads as
more complete than it is.

## Cards

`placed.card` is a card for every node of the tree, in tree order.

| Node | What it owns |
| --- | --- |
| A catalog part | Its own card, the checks `anvilate check` runs on its spec |
| A placeholder | One not-evaluated entry with its reason: a placeholder is never a pass |
| A product, or a sub-product occurrence | The interference between its own children |

A node's status is the worst of its own entries and its children's statuses. Not
evaluated never counts as a pass. A finding is held once, by the node that owns it: a
clash inside `stage/drive[2]` belongs to that drive, and the stage fails by reference to
it. `card.findings()` lists every finding with its owner's path, `card.find(path)` returns
one node, and `str(card)` prints the tree. Every interference entry over a placeholder
says it is provisional and names the placeholders under that node.

## Layout

A layout holds the product's driving parameters. Any value in an item's spec or
placeholder can read one by name, so changing the layout changes every item that reads it,
and no part document is edited.

```yaml
layout:
  parameters:
    - {name: shaft_dia, value: {magnitude: 20, unit: mm}, source: bearing catalogue bore}
definitions:
  - id: collar
    placeholder:
      holes: [{tag: bore, ..., diameter: {layout: shaft_dia}}]
```

`parse_product` puts the value in place and records each reader in the parameter's
`read_by` (`collar:placeholder.holes.0.diameter`). A stored product is checked against
those records, so it cannot claim a reader that no longer holds the value. A name the
layout does not declare is refused. A parameter nothing reads is listed under `unused` and
named by the placed product. The layout is in no parts list and no mass roll-up. A
provisional part number follows the values its item reads.

### Datums

The layout can also fix named datums in the product's frame: a `point`, an `axis` along a
`direction`, or a `plane` normal to one. A mate names a datum as its `on` part, so an item
can sit on a deck height or run on a spindle axis that no part defines.

```yaml
layout:
  datums:
    - {name: deck, kind: plane, direction: z, at: [{magnitude: 0, unit: mm}, {magnitude: 0, unit: mm}, {layout: deck_height}]}
    - {name: spindle, kind: axis, direction: z, at: [...]}
mates:
  - {id: on-deck, kind: face_to_face, place: {part: block, face: bottom}, on: {part: deck, face: top}}
```

| Datum | Offers a mate |
| --- | --- |
| `plane` | The two faces normal to it (`top` and `bottom` for a `z` plane), both through `at` |
| `axis` | Itself, to a `shaft_in_bore` mate naming its direction |
| `point` | Any face or axis through it |

A datum's coordinates can read layout parameters, so a variant can move it. A datum is in
no body, no mass and no parts list. A mate that places a datum, asks a plane for a face it
does not have, or asks a datum for holes is refused.

## Variants

A variant names a set of parameter overrides and definition substitutions against the base
product. `resolve_variant(product, "long")` returns it as a complete product of its own,
`stage-long`, to place and check like any other, so a check that fails only on the long
stage fails there alone.

```yaml
variants:
  - name: long
    parameters: {stroke: {magnitude: 350, unit: mm}}
    substitutions: [{id: motor, identity: {...}, placeholder: {...}}]   # replaces 'motor'
```

Each override reaches every place the base layout records as reading it. A substitute may
read layout parameters too, and gets the variant's values. A substitute that does not offer
the holes or feature a mate uses is refused, naming the mate. A variant that overrides an
undeclared parameter or substitutes an undefined item is refused.

## Interfaces and connections

Items can offer typed interfaces, and a product can connect them by name instead of naming
features in mates; every interface is connected or declared open. See
[Interfaces](interfaces.md).

## Purchased components

A definition can be a bought `component`: a record with its manufacturer, part numbers,
suppliers, envelope, holes and sourced ratings, and the `demands` the product puts on it.
It is placed like a placeholder and checked by its ratings. See
[Purchased components](components.md).

## Placeholders

A placeholder stands in for an item nobody here details yet, such as a bought motor before
it is chosen. It is a box, centred on its own origin.

| Field | What it does |
| --- | --- |
| `envelope`, `mass`, `reason` | The box, what it weighs, and why it is still a placeholder |
| `holes` | Interfaces it offers: `tag`, `x`/`y`/`z` of the entry point, `diameter`, and the `face` it opens on. A `hole_pattern` mate bolts onto them, so the motor's bolt pattern places it now. |
| `center_of_mass` | Measured from the envelope's centre. Left out, the centre is used and the placed product names that placeholder under `center_assumed`. |

A hole or a centre of mass outside the envelope is refused. Any interference result that
involves a placeholder says it is provisional and names the placeholders it rests on.

## At the shell

`anvilate check stage.product.yaml` places the product and prints its summary tree: each
node's path, part number, verdict, finding count and governing finding. A failing node
that owns no finding names the nodes it fails by reference to. Sub-products are read from
the other `*.product.yaml` files in the same folder, by name. `--node stage/drive[2]`
prints that node's full card instead. `--format json` answers with the same tree, and the
exit code is the product's verdict, as for a spec.

`summarize_product(placed, product_tree(product), limit=60)` is the same summary in
Python. Past its bound it keeps the worst nodes and counts the rest.

An agent builds a product through the same `build_combination` tool a combination uses:
the product document goes in `combination`, the sub-products in `library`. It returns the
summary tree as `product`. One more call with `node: "stage/drive[2]"` returns that node's
full card.

`anvilate combine stage.product.yaml --output stage.step` places it, prints the same
summary, and writes one STEP AP242 assembly (`write_product_step` in Python). Each item is
one named product, its part number and description, placed once per occurrence. The export
gate judges the whole tree's card, so a product resting on placeholders is written only
with `--unvalidated` and watermarked so.

## Worked products

Four products ship under [`examples/products/`](../examples/products/), each one placed,
checked and exported in CI. Copy one and change it rather than compose a tree from nothing.

| Product | What it shows |
| --- | --- |
| [`linear_stage`](../examples/products/linear_stage.product.yaml) | A rail pattern whose length a layout parameter drives, a catalog carriage plate, a bought motor, and a `long` variant |
| [`gear_reducer`](../examples/products/gear_reducer.product.yaml) | Gear stages and an output shaft placed on axis datums; one bought stage placed twice |
| [`enclosure`](../examples/products/enclosure.product.yaml) | A catalog box and lid, the lid's lip inside the walls, a board on datum planes, a fan on the lid |
| [`cart_frame`](../examples/products/cart_frame.product.yaml) | A frame on four casters from two patterns, with a catalog deck plate |

Each rests on placeholders for what is bought or not yet detailed, so each is not
evaluated and exports only marked unvalidated.

## Rebuilding what changed

Pass one `BuildCache` to successive `place_product(..., cache=cache)` calls. Each item is
keyed on its content (its spec or placeholder, not its id or part number), so an
unchanged item is reused, built geometry and card alike. Only changed items are built
again. Placement and every check that spans items run on each build. `placed.rebuilt` and
`placed.reused` count distinct items each way, and the summary line says
`1 of 5 items built, 4 reused`. CI holds a warm rebuild equal to a cold build of the same
product.
