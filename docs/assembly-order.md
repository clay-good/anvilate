# Assembly order

A part that fits in the finished assembly may still have no way in. It goes in along a
direction, and on the way it sweeps through space another part may already occupy. If that
part went in first, this one is blocked. `anvilate.assembly` puts every such relation down
and answers whether an order exists. When one does, it names it. When none does, it names
every part in the cycle and what each one sweeps.

## What you get

```python
from anvilate.assembly import InsertionDirection, Part, assembly_order

order = assembly_order([
    Part(name="housing", insertion=InsertionDirection.MINUS_Z, occupies=("shell",)),
    Part(name="retainer", insertion=InsertionDirection.MINUS_Z, occupies=("mouth",)),
    Part(name="lens cell", insertion=InsertionDirection.MINUS_Z, occupies=("bore",),
         sweeps=("mouth",)),
])
order.order      # ("housing", "lens cell", "retainer"): the cell passes the retainer's mouth
order.entry()    # PASS: "a valid order exists: housing -> lens cell -> retainer"
```

## The rules

| Rule | What it means |
| --- | --- |
| A part goes in before whatever occupies its path | If part A's insertion sweeps a feature part B occupies, A must be installed first. The order respects every such relation and otherwise keeps the declaration order, so one declaration always gives one order. |
| No order is a finding, with every member named | Parts that each block another form a cycle. The entry fails naming all of them and each conflict ("bracket sweeps slot b, which clip occupies"), not only the edge that closed the loop. |
| Two parts in one place is an interference | Two parts declaring the same occupied feature cannot both be installed in any order, and the entry says which two. |
| A valid order is a result | It is reported, so a screened assembly reads differently from one nobody screened. |
| Nothing is inferred | The screen reads declarations, never geometry. A part with no insertion direction makes the entry `not_evaluated`, naming it. It is never treated as insertable from anywhere. |

## Reaching an adjustment in the state it is made

A build passes through states, and a part installed in one stays installed in every later
one. An adjustment names the state it is made in and the route a tool takes to it:

```python
from anvilate.assembly import Adjustment, AssemblyState, screen_adjustment_access

states = [AssemblyState(name="open", installs=("housing", "lens cell")),
          AssemblyState(name="closed", installs=("cover",))]
focus = Adjustment(feature="focus screw", performed_in="closed", access=("top opening",))
screen_adjustment_access(states, parts, [focus])
# FAIL: focus screw cannot be reached in closed: cover (installed in closed) occupies top opening
```

The same adjustment made in `open` passes. Routed through a declared side port, it passes
in `closed` too. With no route declared, it is not evaluated: an undeclared route is not a
clear one. An adjustment in a state the build never defines is refused by name.

[`examples/sealed_housing_adjustment.py`](../examples/sealed_housing_adjustment.py) is the whole case: a lens focused after its housing is sealed, through the opening the cover closes, and the revision that routes it through a sealed side port instead.

A service action is the same question as an adjustment: a feature, the state it is done
in, and the route a hand or tool takes to it. Replacing a desiccant cartridge after the
cover is on fails through the top opening the cover closes and passes through a declared
service port, from the same `screen_adjustment_access`.

## A tolerance nobody can measure

`screen_inspectability` takes an `Inspection` per toleranced dimension: the method, and the
features the instrument passes through. A dimension is measurable in a state when nothing
installed by then occupies that route. One measurable in no state fails, naming every state
examined, because a tolerance nobody can verify on the built article is a drawing note
rather than a control. One with no route is not evaluated. A summary states how many
dimensions and states were examined and how many are measurable in none, so a clean result
is distinguishable from one that never ran.

## Whether the tool reaches

A fastener that fits may still be one no tool can turn. A `ToolEnvelope` is the space a tool
occupies while it works, its widest body diameter along its reach, with the source of those
numbers: the library ships no tool dimensions, because the standards that state them are not
redistributable, so they come from the user's tool catalogue or a measurement. An
`AccessRequirement` puts that envelope in front of the tagged face a feature sits on, and
`.keepout()` turns it into a cylinder keepout checked by the same intrusion mechanism as any
other (`anvilate.keepouts.screen_keepouts`), against the part and against the neighbouring
bodies passed in. There is no second collision check. A 20 mm socket reaching a cap screw
through a 14 mm hole in a shelf above it fails, naming the shelf, while the screw head's own
envelope clears; widen the hole to 26 mm and the socket clears by 3 mm.

`screen_tool_access` judges each requirement in the assembly state it is used in: its
neighbours are the parts installed up to and including that state. The same socket that
reaches a screw while the housing is open fails once the shelf is on, and the entry names the
state and the shelf. A requirement with no state is not evaluated, and so is one whose
installed parts were given no geometry, because access is never measured on an assembly with
a part missing.

`screen_swing_arc` asks whether a wrench can turn. A `SwingRequirement` states the handle's
length, width and depth, the height it turns at above the face, and the arc it needs, with
its source: 60° turns a hexagon one flat, 30° is enough for an open-end wrench that can be
flipped. The handle is placed at every degree around the feature and checked against the
neighbours the state has installed, and the largest free run, wrapping through 360°, is the
arc achieved, stated to that 1° sampling. An 80 mm handle between two walls 40 mm either
side of a nut swings 53°, short of 60° and bounded by the walls; with the walls at 70 mm it
swings 115°. There is no closed form for an arbitrary obstruction, so the geometry is
sampled, and the entry says so.

A blocked tool or a short swing carries a directional repair hint the repair loop reads: a
smaller `body_diameter`, because a slimmer tool sweeps a subset of a wider one's space, and a
shorter `handle_length`, because a shorter handle sweeps a subset of a longer one's disc.
Neither is solved to a value, which would take the geometry search again. An adjustment or
inspection blocked by a part has no numeric lever, only a route, so it carries none.

## Declared in the document

A Design Spec can declare the assembly itself: `assembly` carries its states, parts,
adjustments and inspections, and screening reads it. The same sealed housing, written as a
document, fails its focus adjustment in `closed` and passes it moved to `open`, and that move
is one line in `anvilate diff`. An operation in a state the document does not define is
refused naming the state.

## Status

This is part insertion, order feasibility, assembly states, adjustment reachability, tool
envelopes and tool-access sweeps checked as keepouts (`openspec/changes/add-assembly-feasibility`,
1.1–1.4, 2.1–2.6, 3.1, 3.2, 4.1–4.5, 5.1). Not built yet: the rest of the failure-mode entries.
