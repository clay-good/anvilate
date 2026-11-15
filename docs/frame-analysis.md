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

## Out of scope

Plates and shells. Dynamics. Nonlinear material. Buckling eigenvalues. Anything that
wants a mesh.
