# CAE handoff

**Your solver gets the model you declared, not one retyped by hand.** A frame declared
for [frame analysis](frame-analysis.md) is written as an input deck in either of the two
open text formats most finite-element solvers read: a keyword deck (`.inp`) or a
bulk-data deck (`.bdf`). The deck holds the nodes, members, sections, materials,
supports and loads. Each frame you pass is one load case.

```python
from anvilate.cae import frame_deck

deck = frame_deck([wind, gravity], format="bdf")   # two frames, one model, two load cases
deck.write("portal.bdf")                            # and portal.bdf.units.json beside it
print(deck)  # bdf deck: 4 nodes, 3 elements, 2 load case(s) (wind, gravity); N-mm-s-t-MPa; ...
```

## What is in the deck

| | Keyword deck (`.inp`) | Bulk-data deck (`.bdf`) |
| --- | --- | --- |
| Element | `B33`, one per member | `CBAR`, one per member |
| Section | `*BEAM GENERAL SECTION, SECTION=GENERAL`: A, I11 = Iy, I22 = Iz, J | `PBAR`: A, I1 = Iz, I2 = Iy, J |
| Orientation | the member's local y as the section's first axis | the member's local y as the orientation vector |
| Material | E and G on the section, density as `DENSITY=` | `MAT1` with E and G, density as `RHO` |
| Released end | `*RELEASE`, rotations only | pin flags on the bar's end, all six |
| Support | `*BOUNDARY`, one line per held freedom | `SPC1` with the held components |
| Node load | `*CLOAD` | `FORCE` and `MOMENT` |
| Member load | `*DLOAD` `PX`/`PY`/`PZ`, global, per length | `PLOAD1` `FX`/`FY`/`FZ` over the whole length |
| Self weight | `GRAV` on the members with a density | `GRAV`, added to the case by a `LOAD` entry |
| Load case | one `*STEP` each, loads replaced with `OP=NEW` | one `SUBCASE` each, labeled with the frame's name |

**The mesh is the frame.** Each member is one Euler-Bernoulli element between its own
nodes: the element [frame analysis](frame-analysis.md) solves. Your solver should give
the answer Anvilate gave, and where it does not, that is a finding about one of the two.

**Every load names its declaration** in a comment beside it (`node_loads[0].fx at node
B`, `member_loads on beam (0)`), and every node, element, section and material names the
declared one it came from, with its source.

## Units are stated, never implied

Every deck is in newtons, millimetres, seconds, tonnes and megapascals: moments in N·mm,
density in t/mm³, distributed loads in N/mm, gravity 9806.65 mm/s². The system is in the
deck's header and in the sidecar, `<deck>.units.json`, which also holds the counts, the
load cases and the deck's SHA-256. A value a sixteen-column field cannot hold in that
system is refused by name, as is one that is not finite.

## A deck is input, not evidence

The header of every deck says **UNSOLVED INPUT**, and so does its sidecar. Writing a
deck changes no check on any card. Reading your solver's results back as cited inputs
is the next part of this handoff, and is not built yet.

## What is refused

| Refused | Because |
| --- | --- |
| Load cases whose nodes, members or supports differ | one deck holds one model; the cases differ only in their loads |
| A load case with no load | a step of nothing reads as a case that was checked |
| Two load cases with one name | each case is named after its frame |
| A released translation, in a keyword deck | its releases are rotations only; the bulk-data deck's pin flags take all six |
| A deck written to a file of the other format | `portal.inp` that holds bulk data is a deck nobody can open |

## How it is checked

Every deck in the tests is read back by a reader written elsewhere: **pyNastran**
(BSD-3-Clause) for bulk data and **meshio** (MIT) for the keyword format; the package
imports neither. meshio is in the dev extra. pyNastran 1.4 pins NumPy below 2, which the
geometry extra cannot share, so its read-back runs in CI's scheduled optional-adapters
job, which fails if either reader is missing. The read-back has to find:

- the node count and the coordinates in millimetres;
- the section on the right bending axis;
- each member's orientation vector, including a member rolled a quarter turn;
- the pin flags on the released end only;
- each subcase's label and applied force;
- the distributed load's card;
- a total mass equal to the frame's steel, in tonnes.

meshio 5.3 files `B33` as a three-node element. It is the two-node cubic beam, so the
test corrects that one entry rather than bending the deck to it.

## Not yet

Solid and shell meshes of a built part (they wait on the meshing pipeline in local FEA),
loads by tagged face, and reading interface forces and peak values back from result
files.
