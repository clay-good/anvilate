# Interfaces

**What each item offers the rest of a product, stated once and checked wherever it
meets something.** A placeholder or a purchased component publishes named, typed
interfaces: a bolt pattern, a shaft, a bore, a mounting face. A product connects two of
them by name, `bracket.motor_mount ~ motor.flange`, and the mate is derived from the pair.
No feature tag of either item appears in the product.

```yaml
definitions:
  - id: bracket
    placeholder:
      holes: [{tag: b1, ...}, {tag: b2, ...}, {tag: b3, ...}, {tag: b4, ...}]
      interfaces:
        - {name: motor_mount, kind: bolt_pattern, face: top, holes: [b1, b2, b3, b4]}
connections:
  - {on: bracket.motor_mount, place: motor.flange}     # the motor is placed on the bracket
open_interfaces:
  - {at: fan.mount, reason: held by the grille}
```

## The vocabulary

Each kind is located by the face it is on or the axis it runs along, and states the
parameters it requires. A missing parameter is refused, naming it and its unit. An
unknown kind is refused with the nearest known ones.

| Kind | Located by | Requires | Partners |
| --- | --- | --- | --- |
| `mounting_face` | face | — | one |
| `bolt_pattern` | face, and its holes | — | one |
| `tapped_pattern` | face, and its holes | — | one |
| `shaft` | axis | `diameter` | one |
| `bore` | axis | `diameter` | one |
| `pin` | axis | `diameter` | one |
| `hole` | axis | `diameter` | one |
| `keyed_shaft` | axis | `diameter`, `key_width` | one |
| `keyed_hub` | axis | `diameter`, `key_width` | one |
| `rail` | face | `width` | any number |
| `carriage` | face | `width` | one |
| `connector_envelope` | face | `width`, `height`, `depth` | one |

## Which kinds meet, and what each pairing checks

| Pairing | Must agree | Checks |
| --- | --- | --- |
| `bolt_pattern` with `bolt_pattern` | — | hole pattern |
| `bolt_pattern` with `tapped_pattern` | — | hole pattern |
| `mounting_face` with `mounting_face` | — | — |
| `shaft` with `bore` | `diameter` | diameter |
| `pin` with `hole` | `diameter` | diameter |
| `keyed_shaft` with `keyed_hub` | `diameter`, `key_width` | diameter, key width |
| `rail` with `carriage` | `width` | width |
| `connector_envelope` with `connector_envelope` | `width`, `height`, `depth` | — |

A connection the table does not pair is refused before any geometry is built, naming both
kinds and what the first may meet. The hole-pattern check is the one a combination runs:
each pair of holes must line up, held to a micrometre when no tolerance is declared. A
diameter check passes while the shaft is no larger than its bore, and states the
clearance. A width or key width agrees within 0.01 mm.

## Every interface accounted for

The card of the product that declares the connections reports every interface its items
offer that is neither connected nor declared open with a reason, as `unconnected
interfaces`, not evaluated. A kind that takes one partner and meets two is reported as a
failure naming all three interfaces.

The same vocabulary is in the MCP server's `initialize` instructions. The published
schema is the [product document](api/schemas/product-document.schema.json).

Not yet built: interfaces bound to a catalog part's tagged features, joints on
connections, and the interface control table.
