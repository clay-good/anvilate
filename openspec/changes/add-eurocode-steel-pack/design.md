# Design: Eurocode 3 steel pack

## What was read, and what could not be (task 1.1)

EN 1993-1-1 is copyrighted by CEN, sold by the national bodies, and is not readable from
here. The route that worked for ASCE 7 works here too: **go to the public document that
reproduces the clause, not to the pages that paraphrase it.**

| Source | What it gave |
| --- | --- |
| [*Eurocodes: Background and Applications — Design of Steel Buildings*](https://orbi.uliege.be/bitstream/2268/194798/1/Eurocodes%20Background&applications%20design%20of%20steel%20buildings.pdf) (European Commission, JRC; Simões da Silva and Simões, from the 2014 Brussels workshop) | §1.2.2.4 and its Tables 1.1, 1.2 and 1.3, which **state that they reproduce Table 5.2 of EN 1993-1-1**, with clause numbers through §5.5.2. Plus two classifications worked in full, with their intermediate ratios. |

Two mechanics worth keeping. The table pages had to be **read as images**
(`pdftoppm -r 170 -f <page> -png`, then Read the PNG): `pdftotext` drops every ε, α and ψ
and every ≤, so the extracted text of Table 5.2 reads `c t  72` — a plausible limit and a
wrong one. And the report's worked examples are what pin the measurement of `c`, which the
table itself states only as a figure.

**The 2022 edition is not covered.** EN 1993-1-1:2022 renumbered and rewrote parts of §5.5,
and no public document reproducing it was found. So task 1.1 is half done: the 2005+A1:2014
generation is read and implemented, and nothing in the pack claims to answer a design basis
pinning 2022. Task 2.5 (edition differences) waits on the same reading, as does 3.1 for
EN 1993-1-8.

## What is built (task 2.1)

`anvilate.analysis.en1993_classification` — Table 5.2 in full: internal compression parts,
outstand flanges, angles and tubular sections, with the combined bending-and-compression
branches on α and ψ, and a rolled I-section's web and flange classified together under
clause 5.5.2(6)'s "highest, least favourable class" rule.

**Where it refuses rather than defaults.** α, ψ and k_σ describe a stress distribution the
caller computed; the standard's own commentary says the combined case needs the
neutral-axis position and that designers often substitute the compression-only
classification. Guessing one is the failure that looks like an answer, so each is required
and refused by name. An outstand asked for a bending-only class is refused too: Table 5.2
gives it no such column, and inventing one would be this library writing a limit the
standard does not have.

**Three findings the arithmetic produced**, each now a test:

- A tubular section's limits go as **ε², not ε**. At S355 the class 3 limit is d/t ≤ 59,58
  and not ≤ 73,23, and the mistake runs exactly one class optimistic across the whole
  range. A test at S235 alone cannot see it, because ε and ε² are both 1 there.
- The two α branches for an internal part **agree at α = 0,5** (36/0,5 and 396/5,5 are both
  72), and above it the class 1 limit falls away fast — the same ratio that is class 1 at
  α = 0,5 is class 2 at α = 0,51.
- A part wholly in compression (α = 1, ψ = 1) reproduces the compression column on all
  three rows (396/12 = 33, 456/12 = 38, 42/1 = 42), which is the table agreeing with itself
  and the check that ψ is the right way round. A flipped sign would give 124 — the
  *bending* limit — for a column web.

**And one correction to this session's own prose.** The first draft of the module docstring
claimed the ε-for-ε² mistake read a d/t of 60 as class 2 against the standard's class 3. It
is class 3 against class 4. The sweep that catches this is running the arithmetic on every
claim before the claim ships; see also the example's root-radius paragraph, whose first
draft had the error running in the unsafe direction when it is in fact conservative.

## What is built (task 2.2)

`anvilate.analysis.en1993_resistance` — §6.2 cross-section resistance, which is what the
class is for. Tension (§6.2.3, the gross section's plastic resistance against the net
section's ultimate, the smaller governing), compression (§6.2.4), bending with the modulus
its class calls for (§6.2.5(2)), plastic shear with its f_y/√3 (§6.2.6), and the
interactions: the §6.2.8 shear reduction with ρ, §6.2.9.1's axial reduction of the plastic
moment with its a ≤ 0,5 cap, and §6.2.9's biaxial sum.

**Every partial factor is an argument with no default.** γ_M0 and γ_M2 are nationally
determined parameters, and a partial factor that defaults silently is the one number in a
resistance nobody notices is wrong. Bundling the recommended values as typed inputs with a
cited override is task 1.2, and until it exists the factor is stated at every call.

**A typo in the source, recorded rather than reproduced.** The report's Eq. (1.27) prints
`N_pl,Rd = A·f_y/γ_M0` — a verbatim repeat of its Eq. (1.26) — where it means the
net-section ultimate resistance. The surrounding sentence names A_net, f_u and γ_M2, and the
report's own Eq. (1.28) rearranges `N_u,Rd > N_pl,Rd` into
`A_net/A > (f_y/0,9f_u)·(γ_M2/γ_M0)`, which is satisfied only by
`N_u,Rd = 0,9·A_net·f_u/γ_M2`. That identity, swept across the boundary it defines, is a
test.

**Anchored on four published results**, all replayed: an HEB 340's N_c,Rd of 6066,95 kN
(printed 6067,0), and two complete axial-plus-bending reductions. The report rounds its
intermediates — n = 0,30 for 0,29758, a = 0,24 for 0,23745 — so each worked example is
replayed twice, once on the report's own rounded figures (reproducing its printed answer
exactly) and once unrounded, with the 1,21 kNm difference asserted rather than hidden. The
second example is the valuable one: its area ratio comes out 0,545 and clause 6.2.9.1(5)
caps it at 0,5, and leaving the cap out reports **more** resistance than the clause allows.

**Three defects this work turned up in itself**, each now a test:

- `_quantity` hands back each value's own magnitude, so comparing a net area against a gross
  one directly read 8 566 mm² as larger than 100 cm² — the same section in two units, and a
  refusal for a perfectly ordinary net section. Both sides are converted now.
- `biaxial_bending_utilisation` used α and β as exponents with `require_finite` buried in a
  loop, where the exponent census could not see it. `base ** nan` is 1,0 at base 1,0, so a
  NaN exponent returned a utilisation of exactly 2,0 — an ordinary-looking overload. It
  routes through a private helper taking the value positionally now.
- The module docstring first claimed η = 1,0 is conservative for the shear-buckling trigger.
  η divides: a larger η *lowers* the threshold and asks for the check sooner. 1,0 is the
  source's conservative value for η's role in the EN 1993-1-5 resistance and the permissive
  end of this trigger, and saying only the first half was wrong.

## What is not built

Tasks 1.2 to 1.4, 2.3, 2.4, 3.2, 3.3 and 4.1 to 4.4 are untouched, and 1.1 and 2.5 wait on
EN 1993-1-1:2022. §6.2.9.1's second condition for neglecting the axial reduction — the one
on the web's own share — is not implemented either: the source does not state it, so it was
not read, and `axial_reduction_negligible` says in its docstring that a False answer means
only that the first condition does not excuse the reduction.
