# Eurocode 3 steel: what is built, and what each number is

Three modules implement EN 1993-1-1's path from a cross-section to a member: classify it,
take the resistance its class entitles it to, then reduce that for buckling. They are closed
form, unit-typed, and cite their clause.

| Module | Clause | What it answers |
| --- | --- | --- |
| `anvilate.analysis.en1993_classification` | §5.5, Table 5.2 | Is this section class 1, 2, 3 or 4? |
| `anvilate.analysis.en1993_resistance` | §6.2 | What can the cross-section carry? |
| `anvilate.analysis.en1993_buckling` | §6.3 | What can the member carry? |

## The chain, on one section

```python
from anvilate.analysis.en1993_classification import PartStress, rolled_i_section_class
from anvilate.analysis.en1993_resistance import compression_resistance
from anvilate.analysis.en1993_buckling import (
    EuropeanBucklingCurve, flexural_buckling_resistance,
)
from anvilate.units import Quantity

Q = Quantity.parse
section, web, flange = rolled_i_section_class(
    height=Q("340 mm"), width=Q("300 mm"), web_thickness=Q("12 mm"),
    flange_thickness=Q("21.5 mm"), root_radius=Q("27 mm"),
    yield_strength=Q("355 MPa"), stress=PartStress.COMPRESSION,
)                                                        # class 1, web and flange alike
compression_resistance(area=Q("170.9 cm^2"), yield_strength=Q("355 MPa"),
                       partial_factor_m0=1.0)            # N_c,Rd = 6066.9 kN
flexural_buckling_resistance(
    area=Q("170.9 cm^2"), yield_strength=Q("355 MPa"), partial_factor_m1=1.0,
    slenderness=0.75, curve=EuropeanBucklingCurve.C,
)                                                        # N_b,Rd = 4207.6 kN
```

Buckling takes 30.6% off what the cross-section could carry, and the curve is the design
decision: at a slenderness of 1.0 curve a₀ keeps 0.725 of the squash load and curve d keeps
0.467 — **55% apart** on the same member. Two worked examples are in
[`examples/eurocode_section_classification.py`](../examples/eurocode_section_classification.py),
[`examples/eurocode_beam_column_resistance.py`](../examples/eurocode_beam_column_resistance.py)
and [`examples/eurocode_member_buckling.py`](../examples/eurocode_member_buckling.py).

## Which numbers are yours

| | Who supplies it |
| --- | --- |
| **γ_M0, γ_M1, γ_M2** | **Yours, every time.** They are nationally determined parameters and have **no defaults anywhere in this pack**. A partial factor that defaults silently is the one number in a resistance nobody notices is wrong. Note that §6.2's cross-section resistances take γ_M0 and §6.3's buckling resistances take γ_M1: a National Annex may set them apart. Declare them once with an [annex](#the-annex-declared-once) rather than retyping them. |
| **The buckling curve** | Yours. Which of the five curves a member takes depends on its section, grade, fabrication and buckling plane — the standard's Table 6.2, which is not bundled. What *is* bundled is each curve's imperfection factor, which the source prints as a list rather than a table. |
| **α, ψ, k_σ** | Yours, under combined bending and compression. They describe a stress distribution you computed, and the standard's own commentary says the combined case needs the neutral-axis position. Each is refused by name rather than defaulted. |
| **M_cr** | Yours. EN 1993-1-1 does not give the elastic critical moment: it depends on the support conditions, the moment diagram and where the load acts relative to the shear centre, through C₁, C₂ and k factors from the literature. |
| **λ̄_LT,0 and β** | Yours, for the §6.3.2.3 rolled-section method. The source recommends 0.4 as a maximum and 0.75 as a minimum; the recommendation is stated, not applied. |
| **The modulus** | Yours to supply, but the **class chooses which one**: W_pl for class 1 and 2, W_el,min for class 3, W_eff,min for class 4. Handing `bending_resistance` the wrong one for the class is refused, because W_pl for a class 3 section reports a plastic moment the section buckles before reaching. |
| N_cr | Computed, by `anvilate.analysis.column.euler_buckling_load`, which is already π²EI/(KL)². |
| ε, H_f, R_μ, χ, χ_LT, ρ | Computed, from the clause. |

## The annex, declared once

The partial factors and the two parameters of the §6.3.2.3 method are nationally determined.
`recommended_annex()` carries EN 1993-1-1's own values with their citation —
γ_M0 = 1.00, γ_M1 = 1.00, γ_M2 = 1.25, λ_LT,0 recommended as a **maximum** of 0.40 and β as a
**minimum** of 0.75 — and `national_annex` replaces any of them with a member state's:

```python
from anvilate.analysis.en1993_resistance import (
    NationalParameter, national_annex, recommended_annex,
)

annex = national_annex("UK National Annex to BS EN 1993-1-1", overrides=[
    (NationalParameter.GAMMA_M2, 1.10, "NA.2.2 of the UK National Annex"),
])
annex.overridden              # (GAMMA_M2,) — what the state chose
annex.gamma_m0, annex.gamma_m2  # 1.0, 1.1
```

**Every override needs its own citation.** A partial factor differing from the
recommendation is exactly the number a reviewer has to be able to trace, and an uncited one
is a number nobody can check. Parameters you do not override keep the recommendation and
stay marked as such, so the annex is always complete and `overridden` says precisely what
changed.

A value outside the bound the recommendation states — a λ_LT,0 above 0.40, a β below 0.75 —
is **reported, not refused**: `outside_recommendation` names it. A National Annex is
entitled to choose outside the recommendation, and the honest thing is to let you see that
it did rather than enforce a bound the standard frames as advice. A γ below 1 *is* refused,
because it divides a resistance.

Nothing reaches for an annex on its own. The resistances still take their factors as
arguments with no defaults, because a design is worked under one jurisdiction's annex and
the pack cannot know which. What this removes is the retyping, not the decision.

## Where it refuses rather than answers

- An **outstand flange asked for a bending-only class**. Table 5.2 gives it a compression
  column and a combined column and no bending-only column; an outstand with a tension edge
  *is* the combined case. Inventing the missing column would be writing a limit the standard
  does not have.
- **Two moduli at once**, or the wrong one for the class.
- **A net-section tension resistance declared halfway.** `net_area`, `ultimate_strength` and
  `partial_factor_m2` go together or not at all: computing none of them would report the
  gross section as the member's resistance.
- **A partial factor below 1**, which would report more than the characteristic value.

## Three things worth knowing before you use it

**A tube's limits go as ε², not ε.** At S355 the class 3 limit is d/t ≤ 59.58, not ≤ 73.23.
Taking the coefficients on ε instead runs exactly one class optimistic across the whole
range — and a test at S235 cannot see it, because ε and ε² are both 1 there.

**The a ≤ 0.5 cap in §6.2.9.1(5) runs unconservative if you drop it.** A larger area ratio
gives a smaller divisor and a *larger* moment resistance, so an uncapped 0.55 reports
capacity the clause does not grant. The source's second worked beam-column is exactly that
case.

**The two lateral-torsional methods choose different curves from the same geometry.** A
rolled I with h/b ≤ 2 is curve *a* under the general method of §6.3.2.2 and curve *b* under
the alternative of §6.3.2.3. The alternative is the more generous in its working range but
carries a second cap, χ_LT ≤ 1/λ̄_LT², that the general method has no equivalent of. Which
method a design uses is declared, not inferred.

## The edition, and what is not here

This is **EN 1993-1-1:2005+A1:2014**. EN 1993-1-1:2022 renumbered and rewrote parts of §5.5
and could not be read from here, so nothing in the pack answers a design basis pinning it.

The standard is copyrighted by CEN and is not bundled. The clauses, equations and the
limits of Table 5.2 are read from
[*Eurocodes: Background and Applications — Design of Steel Buildings*](https://orbi.uliege.be/bitstream/2268/194798/1/Eurocodes%20Background&applications%20design%20of%20steel%20buildings.pdf),
the European Commission's JRC report from its 2014 Brussels workshop, whose tables state
that they reproduce the standard's. Nine worked results from that report are replayed in the
tests, down to their intermediate ratios — including where the report's own rounding of
λ̄ → Φ → χ makes its printed answer differ from an unrounded one, which the tests state
rather than hide.

Not implemented: the §6.3.3 member interaction formulae, the nationally determined
parameters as typed inputs, steel-grade records by thickness range, European profile
geometry, bolted connections, and fillet welds — the last of these read as far as one
coefficient that could not be sourced either way, which
`openspec/changes/add-eurocode-steel-pack/design.md` records. There is no design-basis
integration yet either, so the edition is a fact about this page rather than something a
spec declares and the pack enforces.
