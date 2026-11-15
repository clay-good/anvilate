# Design notes: Frame analysis

Research done on 2026-10-19.

## Referee and alternative engine

| Library | License | Latest | Capabilities | Decision |
| --- | --- | --- | --- | --- |
| Pynite (PyNiteFEA) | MIT (Copyright 2018 D. Craig Brinck) | 3.2.0, 2026-09-13 | 3D static, P-Δ, modal (frames), pushover, plates, tension/compression-only members, springs; tested against textbook problems in CI | Referee in tests; opt-in engine with version recorded |
| FEM2D | MIT | 0.2.1, 2026 | 2D frames | Not needed |
| anaStruct | GPL-3.0 (to verify) | — | 2D frames | Not adopted (license class) |

Sources: https://github.com/JWock82/Pynite/blob/main/LICENSE, https://pypi.org/project/PyNiteFEA/

The in-house solve exists so that the core needs no optional install to resolve a frame,
and so that the convention on every produced record is Anvilate's own, declared once.
Pynite is the independent answer the tests compare against.

## Why first order by default

A first-order linear elastic solve is the analysis every code's member checks assume
their forces came from, unless the code's own amplification is applied (AISC 360
Appendix 8 B1/B2, EN 1993-1-1 §5.2). Running P-Δ silently and then applying the code's
amplifier would double count. So second order is a declaration, and the member checks are
told which basis their forces have.

## Verification cases

Each re-derived from public solutions and pinned:

| Case | Quantity pinned |
| --- | --- |
| Propped cantilever, uniform load | Reactions, fixed-end moment, maximum deflection |
| Fixed-fixed beam, mid-span point load | End moments, mid-span moment, deflection |
| Three-span continuous beam | Support moments |
| Single-bay portal frame, lateral load | Column moments, sway |
| Space frame with torsion | Torsion in the loaded member |

Each is also solved by Pynite in the test and the two agree within the stated tolerance.

## The product case

`add-product-screening` refuses an indeterminate load path. With a frame declared over
the product's connections (each connection a node, each item's structural members as
members, placeholders as rigid links with declared stiffness or refused), the split is a
solve. The card entry for each part's interface load then depends on the frame entry, and
the frame entry names the declared stiffnesses it rests on, so a placeholder's assumed
stiffness is visible on every number downstream of it.

## Holding the frame to the build

A frame and a combination are two documents about one structure, and nothing held them to
each other: the frame solves, the combination draws and exports, and a member modelling
the wrong part passes every check it has on a force computed for a structure nobody is
building. So a member may name the part it is (`item`) and a node the connection it sits
at (`at`), both declared rather than inferred — two parts whose boxes touch are not
necessarily joined, and a node claiming a connection it is not puts the solve's reaction
on the wrong bolt.

`frame_over_combination_scorecard` reads the two against each other: every `item` is a
part, every part is covered, every `at` is a mate, and each part's modelled length is one
the build can account for.

**That last rule is asymmetric, and that is the design.** A centreline model is *shorter*
than its part by however much of each end the joints swallow — the shipped portal frame
models a 2 m beam as a 1.8 m centreline, and the 200 mm is the two column depths it seats
on. Comparing the two for equality would fail every correct frame. What is refused is a
model **longer** than its part, because no joint adds steel, and a shortfall past twice
the part's section depth, which is the most two joints can account for. Both bounds are
stated rather than a tolerance guessed at.

A frame with no `item` on any member is `NOT_EVALUATED`. Nobody claimed anything, and
agreement is a different fact — reporting it as a pass would make the check vacuous for
exactly the frames that have never been held to a build.
