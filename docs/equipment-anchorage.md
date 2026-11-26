# Equipment anchorage: which coefficients are yours

A machine bolted to a slab needs two numbers nobody can look up for you and one
calculation that is pure geometry. This page says which is which, so you know what to
declare and what the tool will not invent.

## The force, by the edition that governs it

The building code's nonstructural-component chapter gives the horizontal design force on
the equipment itself. **ASCE/SEI 7-22 rewrote the equation**, so the same unit on the same
slab has two different design forces depending on what your jurisdiction adopted. Both
forms are implemented and each names its own edition on every result.

| Edition | Equation | Clause |
| --- | --- | --- |
| ASCE/SEI 7-16 | Fp = 0.4·S_DS·a_p·(1 + 2z/h)·W_p/(R_p/I_p) | Eq. 13.3-1 |
| ASCE/SEI 7-22 | Fp = 0.4·S_DS·I_p·W_p·(H_f/R_μ)·(C_AR/R_po) | Eq. 13.3-1 |

Both are held to the same two bounds, which did not change between the editions: not
required to exceed 1.6·S_DS·I_p·W_p (Eq. 13.3-2), not less than 0.3·S_DS·I_p·W_p
(Eq. 13.3-3). Every result says which of the three produced it, so a force at a bound is
never mistaken for the equation's own answer.

## Yours, ours, and nobody's

| | Who supplies it |
| --- | --- |
| **a_p, R_p, C_AR, R_po** | **Yours.** These are the rows of Tables 13.5-1 and 13.6-1, which are copyrighted and are not bundled. Each arrives as a `TabulatedCoefficient` carrying the table it was read from, and a coefficient with a blank citation is refused rather than used. |
| S_DS, I_p | Yours: the site's spectral acceleration and §13.1.3's importance factor. |
| H_f, R_μ | Computed, from §13.3.1.1 and §13.3.1.2 — the attachment height over the roof height, the structure's approximate period, and its R and Ω_0. |
| The vertical force | Computed: 0.2·S_DS·W_p (§13.3.1.6), the one term no coefficient reduces. |
| The anchor forces | Computed, two ways. By [rigid-base statics](walking-working-surfaces.md#the-post-base-and-the-two-anchors-a-hand-pulls-out) from your mass, centre of gravity, footprint and anchor pattern; or, where the equipment sits on a declared **base frame**, from that frame's solved support reactions. Either way, **no friction relied on**. |
| An anchor's **capacity** | Nobody's, yet. The concrete provisions are not implemented; see what is missing below. |

A non-seismic load — a declared wind pressure on rooftop equipment, a machine's own
dynamic force, an impact allowance — is a load case on the same anchors, and §13.3.1.7
says the larger governs the strength design. So the seismic force goes in as one case
among them, and the answer comes back as the *case* that governs, not just its magnitude:
a wind case that sizes the bolts does not suspend the chapter's seismic detailing.

## What the arithmetic was checked against

ASCE 7 is behind a login and secondary pages disagree with each other about which form
belongs to which edition, so neither was used. The 2022 form is read from
[FEMA P-2082-1, the 2020 NEHRP Provisions](https://www.fema.gov/sites/default/files/2020-10/fema_2020-nehrp-provisions_part-1-and-part-2.pdf),
whose replacement text for §13.3.1 is what ASCE/SEI 7-22 adopted. The 2016 form and both
bounds are read from [NIST GCR 18-917-43](https://doi.org/10.6028/NIST.GCR.18-917-43),
the ATC-120 report behind the rewrite.

That report also tabulates Fp/Wp for archetype buildings, which is what pins the code.
For its four-storey steel ordinary concentrically braced frame with an
unlikely-resonance component, the implementation reproduces **every** published cell of
the row — 0.80, 0.65, 0.51, 0.37 and 0.30 at z/h of 1, 0.75, 0.5, 0.25 and 0 — and each
again after the report's own Ω_0 = 1.5 anchor factor. The last cell is the only published
value anywhere in the report that exercises Eq. 13.3-3's floor.

**One deliberate difference.** ATC-120 recommended a cap of 2.0·S_DS·I_p·W_p; the
Provisions enacted 1.6, which is what is applied. The report's Table 4-13, which prints
its values uncapped, gives 3.21 for that archetype's roof with an elastic component, and
that figure is reproduced too — so the equation is pinned uncapped and the cap applied to
it is the enacted text's, not the recommendation's.

## What the rewrite does to a real base plate

[`examples/roof_cabinet_component_force_by_edition.py`](../examples/roof_cabinet_component_force_by_edition.py)
puts a switchgear cabinet on that archetype's roof. Nothing about the cabinet changes and
the design force goes from 2,256 N to 7,520 N — a factor of **3.33**. It is not the height
term: H_f at the roof is 3.49 against the older linear rule's 3.0, and the building's
ductility factor of 1.34 works in your favour. It is the component. The 2016 equation
credited a cabinet with R_p = 2.5 of its own ductility; the 2022 one asks whether the
cabinet resonates with the building and, for one that does, multiplies by C_AR/R_po.

Two secondary findings from the same example are worth carrying into a real calculation.
The 2022 force is the **cap**, not the equation, so Eq. 13.3-2 is what sizes the anchors
on an ordinary roof-mounted cabinet. And the concurrent vertical force buys only 3.5% more
anchor tension here, because on tall equipment on a tight bolt pattern the weight was
resisting under 15% of the overturning moment to begin with: the lever is everything, and
the repair is the pattern.

## On a base frame, the frame is the better declaration

A skid, a stand or a bolted base frame can go through
[frame analysis](frame-analysis.md) instead: declare its nodes, members and supports, solve
it, and `frame_anchor_demand(frame, solution)` reads each support's reaction as the anchor
demand under it. Uplift is a **negative** vertical reaction — the support holding the frame
down — and the shear is the resultant of the two horizontal ones.

**The two routes agree.** On a four-support skid they give the same governing tension to the
last digit: 16.625 kN either way for one worked case, and 13.687 kN either way once the post
is moved off centre. A direct-stiffness solve and a lever-arm hand calculation are different
models of the same hardware, so their agreement is a check on both.

What the frame route buys is therefore not accuracy — it is that the structure is declared
**once**. The pattern route has to be *told* the centre of gravity, the resultant and the
height they act at; the frame derives all three from its own nodes and loads. Moving that
post is the illustration: the frame knows, and the pattern has to be told again.

One thing it reports that the pattern cannot: a support that declares a **rotational
restraint** carries a moment, and a single anchor bolt is a pin and does not take it.
`FrameAnchorage.restrained` names those supports. The fact comes from the declaration and
never from the size of the reaction — a pinned skid's corners come back with about
10⁻¹⁴ N·m of solver noise, and reading the magnitude named all four of them.

## What is not here

- **Anchor capacities.** The ACI 318 Chapter 17 concrete breakout and pullout provisions
  are not implemented, so this produces a *demand* and nothing checks it yet. That is the
  open half of `add-equipment-anchorage`.
- **Post-installed anchor capacities**, which are product-specific and gated on an
  evaluation report. Those stay user-declared with the report cited.
- **The coefficient tables**, deliberately and permanently.
- **Any statement of code compliance**, or of which edition your jurisdiction adopted.
