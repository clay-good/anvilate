# Purchased components

**A part you buy is a record, not an envelope written from memory.** A motor, a bearing, a
linear guide or a gas spring is stated once with who makes it, where to buy it, the space
it takes, the holes it offers, and its ratings, every value with the datasheet line it came
from. A product places it as an item, and its card checks each rating against what the
product asks of it.

## Writing a record

```yaml
definitions:
  - id: motor
    identity: {description: stepper motor, source: buy}
    component:
      manufacturer: Acme Motion
      part_number: 23HS45-4204
      description: NEMA 23 stepper, 1.26 N·m
      family: motor
      suppliers: [{supplier: Distributor, number: D-23HS45}]
      envelope: [{magnitude: 57, unit: mm}, {magnitude: 57, unit: mm}, {magnitude: 112, unit: mm}]
      envelope_source: datasheet p.1, outline drawing
      mass: {magnitude: 1.4, unit: kg}
      mass_source: datasheet p.1
      ratings:
        - {name: rated_torque, value: {magnitude: 1.26, unit: N*m}, source: datasheet p.2, holding torque}
      holes: [{tag: m1, x: ..., y: ..., z: ..., diameter: ..., face: bottom}, ...]
    demands:
      - {name: torque, value: {magnitude: 0.9, unit: N*m}, source: axis sizing, peak}
```

A component definition is bought, and only a component states `demands`. Its `holes` take
a `hole_pattern` mate the way a placeholder's do, so the motor is placed by its own bolt
pattern.

## Citing a datasheet

Every value a record states carries its source, and the record is refused without it:

| Value | Its source |
| --- | --- |
| `envelope` | `envelope_source` |
| `mass` | `mass_source` |
| each of `ratings` | that rating's `source` |
| `price` | its `source` and `date` |
| each of `demands` | that demand's `source`, where the requirement came from |

A source says where a reader can find the number again: the document, its revision, and the
page, table or drawing note, such as `datasheet rev C p.2, torque table`. A source is never
blank and never a catalog copied into the record: state the values the product uses, each
with its line, and nothing else.

## What each family is checked for

| Family | Ratings the record states | Demands the product states | Check |
| --- | --- | --- | --- |
| `ball_bearing`, `roller_bearing` | `dynamic_load_rating` | `equivalent_load`, `speed`, `required_life` | basic rating life in hours, L10 = (C/P)^p with p = 3 or 10/3, against the required life |
| `motor`, `coupling` | `rated_torque` | `torque` | rated torque against the torque it must deliver |
| `linear_guide` | `stroke`, `dynamic_load_rating` | `stroke`, `load` | stroke, and load against the rating, which product screening's load path supplies |
| `gas_spring` | `force` | `force` | force against the force it must hold |
| `caster` | `load_rating` | `load` | load rating against the load it carries, which product screening's load path supplies |

A record missing one of its family's ratings is refused. A demand the product does not
state leaves its check not evaluated, naming the demand to declare. A demand the family does
not read is refused, so a misspelt one cannot leave its check unrun.

## Sourcing

A record with no supplier part number is unsourced. Its card carries a not-evaluated
`sourcing` entry, so a product holding it never exports as validated.

A record's `price` is its unit price, with its source and date. The product cost roll-up
reads it; a record with no price leaves every node above it incomplete, naming it. See
[product screening](product-screening.md).

## Using a vendor model

A record names the vendor's STEP file by `model: {file, sha256}`, a path relative to the
product's folder. The file is used where it is and never copied. `anvilate check` and
`combine` read it from the document's folder (`place_product(..., root=folder)` in Python),
and the card's `vendor model` entry says:

| What it finds | Entry |
| --- | --- |
| The file, unchanged, measuring within 0.5 mm of the record's envelope on every axis | pass |
| The file, unchanged, outside that | fail, naming the difference |
| No folder, no file, or a file whose SHA-256 is not the recorded one | not evaluated: the geometry is not checked |

## Drafting a record from a vendor model

`draft_component(path, manufacturer=..., part_number=..., description=..., family=...,
mass=..., mass_source=..., ratings=...)` measures the vendor's STEP: its envelope, and each
hole along x, y or z as a hole on the face it opens on (`h1`, `h2`…), with the model's path
and hash. Ratings and mass come from the datasheet and are yours to state. The record is
`drafted`, and a product holding it carries a not-evaluated `drafted record` entry until
`confirmed_by` names who checked it against the datasheet.

Not yet built: bundled dimension tables for common families.
