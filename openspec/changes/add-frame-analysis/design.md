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
