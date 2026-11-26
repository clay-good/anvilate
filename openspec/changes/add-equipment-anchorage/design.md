# Design: Equipment anchorage

## What is built: the statics (task 2.1)

`anvilate.analysis.anchorage` takes an anchor pattern, a weight, a centre of gravity and
a lateral force at a height, and returns what each anchor is asked to carry. It produces
a **demand**; what an anchor can take is a concrete or steel capacity with its own
edition and factors, and is not here.

The model is stated in the module, because every term of the answer depends on it: a
rigid base, anchors in tension only, tension divided by lever arm, shear divided equally,
and **no friction relied on**.

**Source.** Drake and Elkin, "Beam-Column Base Plate Design — LRFD Method", *AISC
Engineering Journal*, First Quarter 1999, pp. 29-38 — read in full from AISC's own free
copy, not recalled. Its Equations 16 and 17 take moments about the anchor tension force,
and its two statements about the rod group are the ones this keeps: *"all the base plate
anchor rods are considered effective in sharing the shear load"*, and *"all of the base
plate anchor rods are not considered effective in sharing the tension load"*.

**Where it simplifies the paper, and why.** Drake and Elkin solve a quadratic for the
bearing length from the concrete's bearing stress and the plate's width, and put the
compression resultant at the centroid of that bearing area. That needs a concrete
strength and a plate size, which an anchor pattern alone does not state. Taking the
resultant at the leeward anchor row needs neither and is conservative: the real bearing
centroid is further out, which is a longer lever arm and less tension.

**The governing direction is a sweep, not a solve**, and says so. The finding it produced
is worth the function: the worst direction is **across the pattern's short side**, where
the lever is least — a 400 x 100 mm pattern takes 4.2 times the tension across its short
dimension that it takes along its long one. On a square the axes are worst and the
**diagonal is the mildest**, which is the opposite of how it looks: the diagonal does
concentrate the moment on one corner, and it also lengthens every lever, so the sum of
squares in the denominator grows faster than the lever in the numerator. The first draft
of the docstring claimed the diagonal was worst; the arithmetic refused it.

## What was read, and where (tasks 1.1, 1.2, 1.3)

Task 1.1 asks for the two editions' §13.3.1 to be **read**, not recalled. ASCE 7 itself
still cannot be read from here, and the secondary pages that paraphrase it still disagree
with each other — several present the 7-16 form under a 7-22 heading. What unblocked this
was going to the **US-government documents the editions were written from**, which are
public and were not tried in the first pass:

| Source | What it gave |
| --- | --- |
| [FEMA P-2082-1, 2020 NEHRP Provisions](https://www.fema.gov/sites/default/files/2020-10/fema_2020-nehrp-provisions_part-1-and-part-2.pdf) | "SECTION 13.3.1 SEISMIC DESIGN FORCES. Replace Section 13.3.1 with the following" — the replacement text ASCE/SEI 7-22 adopted. Eqs. 13.3-1 to 13.3-6, §13.3.1.6's vertical force and §13.3.1.7's non-seismic rule, in full. |
| [NIST GCR 18-917-43](https://doi.org/10.6028/NIST.GCR.18-917-43) (ATC-120) | ASCE/SEI 7-16's Eq. 13.3-1 restated in its §4.1, and both bounds in its §4.4 and §4.5. Also the archetype tables that pin the arithmetic. |

The earlier fema.gov 403 was the site refusing one path, not the document being unavailable.
The lesson worth keeping: **a copyrighted standard's equation structure usually has a
public ancestor**, because the NEHRP Provisions and the NIST report behind a code change
are government work. Looking for the ancestor beats reading the paraphrases.

`anvilate.analysis.nonstructural_seismic` implements both forms, each naming its edition on
every result, under the user-supplied-allowables doctrine: `TabulatedCoefficient` carries a
value, its symbol and the table it was read from, and a blank citation is refused. H_f and
R_μ are computed; S_DS, I_p and the table rows are the document's.

**How it is pinned.** NIST GCR 18-917-43 Tables 4-12, 4-13 and 4-14 tabulate Fp/Wp for
archetype buildings at S_DS = 1.0. The four-storey steel OCBF row reproduces cell for cell
— 0.80, 0.65, 0.51, 0.37 and the 0.30 floor, each again after the report's Ω_0 = 1.5 — and
Table 4-13's uncapped 3.21 reproduces too, which pins the equation before any bound is
applied. Five cells is enough to pin the 0.4 constant, both of H_f's terms, R_μ, and both
tabulated coefficients at once, because no other combination of them lands on all five.

Two differences from the report are recorded rather than smoothed over. ATC-120 recommended
a 2.0·S_DS·I_p·W_p cap and the Provisions enacted 1.6, which is what is applied. And the
report carries the building's R_μ down to z/h = 0, where §13.3.1.2 as enacted sets R_μ = 1.0
— the two readings land on either side of Eq. 13.3-3's floor, which is why R_μ is the
caller's and not computed inside the force.

## What task 2.2 needs that does not exist yet

The proposal says Anvilate "has the last step (the structural pack's cast-in anchor
breakout and pullout screens)". It does not: there is no breakout or pullout screen in
the tree today. Task 2.2 is therefore a build, not a wiring-up, and it is a concrete
capacity under ACI 318 Chapter 17 with the same copyright question as the force.
