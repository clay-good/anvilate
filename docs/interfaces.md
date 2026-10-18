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

## Interfaces on catalog parts

A catalog part's interfaces are bound to its tagged features and read from the built part,
never restated:

```yaml
  - id: plate
    spec: {...}                    # a mounting plate with its m6 hole pattern
    interfaces:
      - {name: motor_mount, kind: bolt_pattern, features: [m6_1_1, m6_2_1, m6_2_2, m6_1_2]}
      - {name: pilot, kind: bore, features: [cb]}
```

A pattern's holes and the face they open on come from the built holes, and a shaft's,
bore's, pin's or hole's axis and diameter from its one round feature, so a change to the
holes changes the interface. `face` may name the far face of through holes. A part offers
the kinds its features state fully (mounting face, patterns, shaft, bore, pin, hole); a
rail, carriage, keyed shaft or connector is offered by a placeholder or component. A
binding to a tag the built part lacks is refused, naming the interface and the tag.

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

## Joints

A connection may declare how the placed item moves:

```yaml
connections:
  - on: base.pivot          # a hole along y
    place: arm.pivot        # a pin along y
    joint: {kind: revolute, range: [{magnitude: 0, unit: degree}, {magnitude: 90, unit: degree}]}
```

The axis is the `on` interface's, through its bound feature on a catalog part or the item's
own axis. Any joint but a rigid one needs two interfaces that define an axis, so a revolute
joint on two mounting faces is refused, naming the connection. A revolute or cylindrical
joint's range is in angles and a linear one's travel in lengths; a ball or rigid joint
states none. `placed.joints` lists each with its axis in the product's frame and its range,
for a swept keepout or a robotics export to read. The connection's `joint sweep` entry turns
or slides the moving item through its range, in steps of at most 15 degrees or ten steps of
travel. It fails naming the body it overlaps most and the step where it does. When it
clears, it reports its least gap over the sweep, where, and between which bodies, to the
items it shares no mate or connection with (those it does touch it by design). A product's
`min_clearance` holds that gap too: a hinged arm that clears a stop 5 mm away at rest comes
within 3.219 mm when it is turned 5 degrees, and fails a 4 mm clearance.

## The interface control table

Every placed product carries `placed.interfaces`: one row per connection, with the product
that declares it, both interfaces, their kinds, the values each states (a pattern's hole
count and face, a shaft's diameter), each item's owner (make, buy or reference, and its
part number), and the connection's checks with their verdicts; then one row per interface
declared open, with its reason. `to_csv()` writes it as CSV, with any cell a spreadsheet
would run as a formula quoted, and `section()` as a report section.

The same vocabulary is in the MCP server's `initialize` instructions. The published
schema is the [product document](api/schemas/product-document.schema.json).
