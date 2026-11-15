# Frame analysis

**The member forces, solved rather than typed.** Every member check in this library takes
the force in that member as an input. For a simply supported beam an agent can work it
out; for a portal, a skid or a two-bay rack it cannot, and the only way in was a doorway
for forces an external solver produced.

A first-order, three-dimensional, linear-elastic direct-stiffness solve, in the core, in
pure Python — no optional install to resolve a frame.

```python
from anvilate.frame import Frame, FrameMember, FrameNode, Freedom, Support, solve_frame

solution = solve_frame(frame)
print(solution)
# portal [first_order_elastic]: 3 members solved over 8 free degrees of freedom,
# equilibrium residual 1.82e-11 N
print(solution.forces("column").axial)       # tension positive
print(solution.displacement("top").ux)
```

## Four rules

**First order by default; second order is a declaration.** A code's member checks assume
first-order forces unless the code's own amplification is applied (AISC 360 Appendix 8
B1/B2, EN 1993-1-1 §5.2). Solving P-Δ silently and then applying the code's amplifier
would double count, so the basis travels on every force record and the check is told
which it has.

```python
solve_frame(frame, basis=AnalysisBasis.SECOND_ORDER)
```

builds each member's geometric stiffness from its own axial force and re-solves until
those forces stop moving. The base moment of a swaying cantilever then comes out exactly
`Hh + PΔ`, which is the defining relation and the test that says the geometric term is
right rather than merely bigger. A frame driven past its elastic critical load is
refused: the softened matrix stops being positive definite, which is the buckling this
analysis can see.

**A mechanism is named, never solved around.** A frame with a free mode has no unique
answer. `solve_frame` raises `MechanismFound` naming the node and the freedom that moves
under no stiffness, instead of the numbers a regularised matrix would return.

**Equilibrium is reported.** Every solution carries the largest out-of-balance force
between its reactions and everything applied. A solver that does not check its own
arithmetic is one nobody checks.

**The convention is stated once and travels.** Local x runs start to end. Local z is as
near the global vertical as the member allows — a column has no such reference, so the
global X axis is used instead, which is why a column's bending axes are defined at all.
`roll` turns the local axes about the member. `axial` reports tension positive, which is
what a member check reads.

## The card it produces

```python
from anvilate.frame import DeflectionLimit, screen_frame

screening = screen_frame(frame, limits=(
    DeflectionLimit(node="mid", limit=Quantity.parse("20 mm"),
                    source="the project's deflection limit, specification §3.2",
                    freedom=Freedom.UZ),
))
```

The solve is a check of its own and comes first, carrying the equilibrium residual and
the analysis that was run. Every deflection entry then says what it was computed from, so
a verdict at the end of a factorisation reads as resting on one rather than appearing out
of nowhere. A limit with no source is refused: a deflection limit is a decision somebody
made, and a number with no author is one nobody can argue with.

A mechanism is one `not_evaluated` entry naming the free freedom and **no deflection
entries at all** — a limit judged against displacements that do not exist would be a
verdict on nothing.

## Member checks on solved forces

`frame_check_node(frame)` is the frame as one node of a
[dependency chain](check-dependencies.md), producing `<member>.axial`,
`.shear_y`, `.shear_z`, `.torsion`, `.moment_y` and `.moment_z`. A member check declares
what it consumes and is then ordered after the solve, fed the solved number, and — the
part that matters — reported `not_evaluated` **naming the frame** when the frame did not
solve. A member check handed a default in place of a force nobody computed is the silent
green the rest of this library refuses.

The moments and shears handed downstream are the governing end by magnitude: a member
check takes one number, and the end that is not governing is not it.

## A frame over the combination it models

A frame and a combination are two documents about one structure, and nothing held them to
each other: the frame solves, the combination draws and exports, and a member modelling
the wrong part passes every check it has on a force computed for a structure nobody is
building.

So a member may name the part it is, and a node the connection it sits at:

```python
FrameMember(name="lc", start="base_left", end="top_left",
            section=ipe200, material=a36, item="left_column")
FrameNode(name="top_left", x=Q("0 mm"), y=Q("0 mm"), z=Q("1500 mm"), at="left_seat")
```

`frame_over_combination_scorecard(frame, built)` then reads the two against each other:

| Check | What fails it |
| --- | --- |
| Members name built parts | a member whose `item` is not a part of the combination |
| Every built part is covered | a part no member names — it carries no force in the solve and will carry load in the shop |
| Member lengths are ones the build can account for | a member **longer** than its part, or short by more than two joints' worth |
| Nodes sit at mates of the build | an `at` that is not a mate of the combination |

**The length rule is asymmetric, on purpose.** A centreline model is *shorter* than its
part by however much of each end the joints swallow — the shipped portal frame models a
2 m beam as a 1.8 m centreline, and the 200 mm is the two column depths it seats on — so
the two are not compared for equality. What is refused is a model **longer** than its
part, because no joint adds steel, and a shortfall past twice the part's section depth,
which is the most two joints can account for and so marks a member modelling a different
part.

A frame with no `item` on any member is `NOT_EVALUATED`, not agreement. Nobody claimed
anything, and that is a different fact from the two documents agreeing — reporting it as
a pass would make the check vacuous for exactly the frames that need it. The node check
is absent, rather than a pass, when no node names a connection.

## What the declaration refuses

| | |
| --- | --- |
| A member at a node the frame does not have | named, before it is a singular matrix |
| A node no member reaches | it is free in all six freedoms |
| A support that restrains nothing | that is not a support |
| A node declared twice, or supported twice | two answers to one question |
| A section property or modulus of zero | a release stated as a section |
| A freedom released at both ends of a member | free in that mode, and a mechanism through it |
| Self weight asked for with no density anywhere | the load would be zero and read as applied |
| More nodes than the cap | see below |

## The cap, and what the external doorway is still for

The factorisation is dense and in pure Python, so it is cubic in the free degrees of
freedom. Measured: 20 nodes in 0.01 s, 60 nodes in 0.2 s, 120 nodes in 1.5 s. Twice that is
twelve seconds and four times is a minute and a half, so `MAX_NODES` is 120 and a larger
frame is refused by name.

That is what [`anvilate.interop`](analysis-interop.md)'s member-force doorway is still
for, and it is not going away: a building model, a plate or shell model, a modal or
buckling analysis, and anything whose engine your office has already qualified all come
in through it. This module exists so the common small frame needs no second tool, not so
the second tool becomes unnecessary.

## How it is checked

Five closed forms, each re-derived rather than taken from this code, and run in every
suite:

| Case | Pinned |
| --- | --- |
| Simply supported beam, mid-span load | `PL/4`, `PL³/48EI`, `P/2` |
| Propped cantilever, uniform load | `wL²/8`, `5wL/8`, `3wL/8`, mid-span `wL⁴/192EI` |
| Fixed-fixed beam, mid-span load | end and mid-span `PL/8`, `PL³/192EI` |
| Three-span continuous beam, uniform load | support moments `0.1wL²`, reactions `0.4wL` and `1.1wL` |
| Cantilever column, lateral tip load | `Ph³/3EI` and the base moment |

Then **Pynite** (MIT, an independently written solver) solves a portal frame, a space
frame with torsion and the P-Delta column, and the two agree to nine significant figures. It is in the dev
extra, so CI always has it; the closed-form cases run without it.

Two mistakes the referee caught, both recorded in the code where they were made: the
congruence transform the wrong way round (which leaves the matrix symmetric and positive
definite, so every beam-only case still passes), and a released end whose *stiffness* was
condensed and whose *fixed-end load* was not (which left a hinge carrying `wL²/12`, the
number a fixed end carries).

## Worked end to end

[`examples/skid_frame_solved.py`](../examples/skid_frame_solved.py): a skid whose four
legs under two tied longitudinals are one redundancy more than statics can resolve. The
solve says the loaded longitudinal takes about ten times the bending of the far one, the
member checks run on those moments and say so, and the skid fails on strength while
passing serviceability.

## Out of scope

Plates and shells. Dynamics. Nonlinear material. Buckling eigenvalues. Anything that
wants a mesh.
