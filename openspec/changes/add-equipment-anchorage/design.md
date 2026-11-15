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

## What is blocked: the ASCE force (tasks 1.1, 1.2, 1.3)

Task 1.1 asks for ASCE 7-16 §13.3.1 and ASCE 7-22 §13.3.1 to be **read**, not recalled.
They could not be read from here:

| Source tried | Result |
| --- | --- |
| ASCE's own §13.3.1 (amplify.asce.org) | 302 to an authenticated login |
| FEMA P-2082-1, 2020 NEHRP Provisions (fema.gov) | 403 Access Denied |
| The same at nibs.org and nehrp.gov | 404, and an expired certificate on the mirror |
| California HCAI and BSC documents reproducing it | the equations are images, not text |

Secondary sources **disagree**: several pages present the ASCE 7-16 form
(`a_p`, `R_p`, `1 + 2z/h`) under a 7-22 heading, and the ones that do give the 7-22 form
differ on the symbol set. Implementing from them would be the exact failure this repo has
already recorded once — an edition shipped from memory, and a formula that was wrong in
both of its two errors at once.

So the force half waits for a readable primary text. What is built below it does not: the
statics take the lateral force as declared, whatever its origin, which is what the
proposal says they should.

## What task 2.2 needs that does not exist yet

The proposal says Anvilate "has the last step (the structural pack's cast-in anchor
breakout and pullout screens)". It does not: there is no breakout or pullout screen in
the tree today. Task 2.2 is therefore a build, not a wiring-up, and it is a concrete
capacity under ACI 318 Chapter 17 with the same copyright question as the force.
