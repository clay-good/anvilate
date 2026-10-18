# Design notes: Drive trains

Research done on 2026-10-17. Every standard below is paywalled except where noted; the
"anchor before implementing" rule applies: no method ships from a remembered edition.

## Standards the checks cite

| Check | Standard (edition verified 2026-10-17) | Source |
| --- | --- | --- |
| Gear rating, basic principles and validity range | ISO 6336-1:2019 (confirmed current 2025): pressure angle 15° to 25°, helix angle up to 30°, transverse contact ratio 1.0 to 2.5 | https://www.iso.org/standard/63819.html |
| Pitting, bending | ISO 6336-2:2019, ISO 6336-3:2019 | https://www.iso.org/standard/63821.html |
| Material strength | ISO 6336-5:2016 | AFNOR listing |
| Variable-load life | ISO 6336-6:2019 | https://www.iso.org/standard/63823.html |
| AGMA rating (metric) | ANSI/AGMA 2101-E25 (2025). New reverse-bending factor and mesh load factor | https://www.geartechnology.com/decades-in-the-making-ansi-agma-2101-e25 |
| Gear geometry | ISO 21771-1:2024 | https://www.iso.org/es/contents/data/standard/08/49/84949.html |
| Basic rack | ISO 53:1998 | https://www.iso.org/standard/22643.html |
| Accuracy classes | ISO 1328-1:2013 | SCC listing |
| Thermal capacity | ISO/TR 14179-1:2001 (heat balance; 25 °C ambient, 95 °C sump baseline); AGMA 947-A23 is its renamed, revised AGMA form | https://www.iso.org/standard/34636.html |
| Bearing life | ISO 281:2007 | SCC listing |
| Splines (later) | ISO 4156-1:2021 (the 2005 edition is withdrawn) | https://www.iso.org/standard/36497.html |
| Enclosed drives (review topics) | ANSI/AGMA 6113-B16 (R2021) | ANSI webstore |

**Withdrawn, so not cited:** ISO 1340:1976 (data on cylindrical gear drawings) and ISO 1341.
No current standard defines the drawing data block, so Anvilate defines its fields and
cites each term to ISO 21771-1 and ISO 1328-1.

## Why mobility is a consistency check, not a count

The Grübler–Kutzbach count misreads overconstrained mechanisms (three co-linear hinges
count −1 and still move), and a gear train with its bearings is overconstrained in 3D.
`add-product-screening` already reports the count as a first-pass figure. A drive train's
real question is whether every shaft's speed is determined exactly once, and that is a
graph check with a definite answer.

## Libraries considered

| Library | License | Decision |
| --- | --- | --- |
| freecad.gears | GPL-3.0 | Reference only |
| python-gearbox (AGMA 2101-D04, ISO 6336) | LGPL-2.1, last push 2020 | Reference only |
| gearpy | GPL-3.0 | Out of scope (time-domain) |
| Coal (hpp-fcl), python-fcl | BSD | Candidates for distance queries if the kernel's own distance is too slow over a sweep |
| build123d joints | Apache-2.0 | Joints place once and keep no live link; the sweep recomputes placements itself |

## Golden test

Shigley's *Mechanical Engineering Design*, Chapter 18, "Power Transmission Case Study",
published free by McGraw-Hill:
https://highered.mheducation.com/sites/dl/free/0073398209/1036702/Chapter18.pdf
(probably the 10th edition; confirm the edition before citing it in a test).
20 hp at 1,750 rpm, output 82 to 88 rpm, compound reverted layout, 12,000 h life. Teeth
16/72 and 16/72; ω3 = 388.9 rpm, ω5 = 86.42 rpm; T2 = 60.0, T3 = 270, T5 = 1,215 lbf·ft;
P = 6 teeth/in; face widths 1.5 in and 2.0 in; Wt23 = 540.0 lbf, Wt45 = 2,431 lbf. Its
rating is AGMA in textbook form, which matches the existing mesh screen.

## Market evidence

CAD-bench (ICML 2026): agents built a right-angle gearbox that looked right in most
attempts and scored about 4% on its functional check. https://icml.cc/virtual/2026/77860
