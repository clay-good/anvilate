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

## What each family is checked for

| Family | Ratings the record states | Demands the product states | Check |
| --- | --- | --- | --- |
| `ball_bearing`, `roller_bearing` | `dynamic_load_rating` | `equivalent_load`, `speed`, `required_life` | basic rating life in hours, L10 = (C/P)^p with p = 3 or 10/3, against the required life |
| `motor`, `coupling` | `rated_torque` | `torque` | rated torque against the torque it must deliver |
| `linear_guide` | `stroke`, `dynamic_load_rating` | `stroke`, `load` | stroke, and load against the rating |
| `gas_spring` | `force` | `force` | force against the force it must hold |

A record missing one of its family's ratings is refused. A demand the product does not
state leaves its check not evaluated, naming the demand to declare. A demand the family does
not read is refused, so a misspelt one cannot leave its check unrun.

## Sourcing

A record with no supplier part number is unsourced. Its card carries a not-evaluated
`sourcing` entry, so a product holding it never exports as validated.

Not yet built: bundled dimension tables for common families, vendor STEP files referenced by
path and hash, and drafting a record from a measured vendor STEP.
