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

## Status

This is part insertion and order feasibility (`openspec/changes/add-assembly-feasibility`,
1.4, 2.4, 4.3 and 4.5). Not built yet: assembly states, tool envelopes and access, swing
arcs, and serviceability. Those need the keepout mechanism, and the Design Spec cannot declare
parts yet.
