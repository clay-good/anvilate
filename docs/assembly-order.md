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

## Status

This is part insertion, order feasibility, assembly states, adjustment reachability, tool
envelopes and tool-access sweeps checked as keepouts (`openspec/changes/add-assembly-feasibility`,
1.1–1.4, 2.1, 2.4, 4.1–4.5). Not built yet: the swing-arc screen, access evaluated per
assembly state on geometry, serviceability and inspectability, the failure-mode entries and
the sealed-housing example.
