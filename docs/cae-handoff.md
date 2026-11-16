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
deck changes no check on any card. A result counts only when it is read back, below,
with the file's hash and what produced it.

## Reading interface loads back

Your solver's answer comes back as the forces on one free body, case by case: the forces
at each interface you cut it at, and any load applied to it. Write them as a CSV with
`case, interface, point, x, y, z, fx, fy, fz, mx, my, mz`, one row per point, which every
solver's grid-point force output can become.

```python
from anvilate.cae import read_interface_forces

imported = read_interface_forces("gpforce.csv", solver="your solver", version="2026.1",
                                 units="N-mm", coordinate_system="basic")
imported.at("base")    # each case's resultant at the base, about its points' centroid
imported.unbalanced    # the cases whose free body does not sum to zero
```

| Read back | How |
| --- | --- |
| Each interface, each case | the summed force, and the moment about the centroid of that interface's points, in N and N·mm |
| Each case's balance | the summed force and moment over the whole free body, held to `tolerance` (0.001 by default) times the largest force and the largest moment any one row brings |
| Where it came from | the file's SHA-256, the solver and version as you declared them, the unit system, the coordinate system |

**A file without its unit system is refused**, naming the file and the systems it may
declare: N-mm, N-m, kN-mm, kN-m, lbf-in, lbf-ft, kip-in and kip-ft. The coordinate system
is recorded and not acted on: nothing here rotates a force.

**An unbalanced case is reported, never corrected.** The bracket in the tests carries
1 kN at its tip, 100 mm out, on four bolts at ±20 mm: the bolts at +20 pull 1,500 N each
and those at −20 push 1,000 N, and the case balances. Raise the tip to 1.1 kN without
changing the bolts and the case is named with its residual: 100 N, and 8,000 N·mm about
the points' centroid 80 mm away.

## A fastener pattern on the imported loads

`fastener_group_on_import` takes each case's load at one interface and shares it over a
bolt pattern by the [fastener group](structural-hand-methods.md) method: NASA TM X-73305
§B1.1.1 for the shares, NASA-STD-5020B §4.4.4 for each fastener's interaction.

```python
from anvilate.cae import fastener_group_on_import

result = fastener_group_on_import(pattern, imported, "base",
                                  coordinate_system="basic", away="+z")
result.governing_case, result.governing_index, result.not_evaluated
```

| Rule | Why |
| --- | --- |
| The pattern must be in the import's coordinate system | nothing here rotates a load; a different system is refused, naming both |
| The pattern carries the opposite of the force on the free body | an imported load is what the pattern does to the part |
| `away` is the direction the part leaves the pattern; tension is the pull along it | a push bears on the plates and carries no bolt tension |
| A case that carries a moment about an in-plane axis is not evaluated | the group method shares shear, twist and tension, not prying; dropping that moment would pass a joint it does not check |
| A case whose free body did not balance is not evaluated | its loads are not a load case yet |

Each case keeps its shear, twist, tension and out-of-plane moment, and the result names
where every load came from. The test pattern is four bolts at ±20 mm under a 1 kN side
load 100 mm out: 250 N direct and 883.9 N from the twist put the worst bolt at 1,075.3 N.

## What is refused

| Refused | Because |
| --- | --- |
| Load cases whose nodes, members or supports differ | one deck holds one model; the cases differ only in their loads |
| A load case with no load | a step of nothing reads as a case that was checked |
| Two load cases with one name | each case is named after its frame |
| A released translation, in a keyword deck | its releases are rotations only; the bulk-data deck's pin flags take all six |
| A deck written to a file of the other format | `portal.inp` that holds bulk data is a deck nobody can open |
| A result file with no unit system, or one not listed | a number without its units is the error this whole handoff exists to stop |
| A result row whose value is not a finite number, or that names no case or interface | it is refused at its line, not skipped |

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
loads by tagged face, reading a solver's native result files (the CSV above is the
doorway until then), the lug, fitting, weld-group and bearing screens on imported cases (the fastener
pattern takes them today), and peak values read from a tagged region.
