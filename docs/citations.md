# What a citation on a result means, and how to check it

Every scorecard entry can carry a `reference`, and every worked derivation carries a
`citation`. This page says exactly what that claim is — and, just as importantly, what
it is not.

## What it means

A citation names **the source of the relation that was evaluated**. It is a pointer for a
reviewer: go to that clause, that table, or that page, and you will find the formula this
number came out of.

```python
entry.reference          # 'NDS'
entry.derivation.citation # 'AISC 360-22 §F2.1'
```

It means all three of these:

1. **The formula is transcribed from the named source.** Not adapted, not a
   simplification with the same name.
2. **The stated limits of that source apply**, and where they are sharp the code enforces
   them. `stokes_settling_velocity` refuses past the Reynolds number its own docstring
   names; `nds_euler_buckling_stress` refuses past the §3.7.1.4 slenderness cap rather
   than quoting the small, plausible stress the formula still yields.
3. **The numbers you supplied were used as given.** Nothing was defaulted in behind your
   back — see below.

## What it does not mean

- **It is not a code stamp.** Anvilate is a screening library. A green scorecard means
  the screened limit states screen clean, not that the design satisfies the code or that
  anyone has taken responsibility for it. The engineer of record owns the design.
- **It does not certify the input values.** A citation on the *method* says nothing about
  the allowable stress, material property, or load you passed in. Those carry their own
  provenance, separately.
- **It does not mean every limit state was checked.** Each entry cites the check it *is*.
  Read the whole card, and read the pack's scope section for what it deliberately leaves
  out — a pack screens the limit states it names and no others.
- **It is not a promise of coverage.** About 12% of the public analysis surface does not
  yet name a source at all; that debt is enumerated in
  [`docs/api/uncited-symbols.txt`](api/uncited-symbols.txt) rather than hidden.

## How to verify one

**1. Read the substituted line.** The [calculation report](calculation-reports.md)
prints the formula, then the same formula with every symbol replaced by its value, then
the result. Do the arithmetic:

```
σ_b = M · c / I
σ_b = 1500000.00 N·mm · 50.00 mm / 2100000.00 mm⁴
σ_b = 35.7 MPa
```

That line multiplies out to the number under it, and every derivation the packs build is
asserted to, in both unit systems, by
`test_every_derivation_the_library_builds_evaluates_to_its_own_result`. If it does not for
some check you are reading, that is a bug worth reporting — it has been one twice, and
the units layer was the cause both times.

**2. Check the glossary.** Every symbol in a derivation is defined in plain language with
its value and unit. A symbol appearing bare in the substituted line means an input was
not declared, and the report labels that section unworked rather than presenting it as
complete.

**3. Go to the source.** The citation is specific enough to find. Anvilate does not
redistribute copyrighted tables, so you will need your own copy of the standard — which
is the point: the number you check against should be yours, not ours.

**4. Confirm the inputs are the ones you meant.** The `assumptions` list on a report and
the entry's `detail` line both echo what actually went in. Where an input carries a
condition, it is carried with it — an `AllowableStress` records the temperature its value
was read at, and the check refuses rather than silently applying a 200 °C allowable to a
400 °C line.

## Where an input's own provenance lives

Bundled standard data — pin dimensions, pipe schedules, bearing boundary dimensions,
material properties — carries a per-property citation you can read back:

```python
pipe = default_pipe_schedule_table().get("4", "40")
pipe.citations()["wall_thickness"].source     # 'ASME B36.10M ...'
pipe.citations()["wall_thickness"].retrieved  # when it was captured
```

Values *you* supply carry your provenance instead, which is the doctrine: Anvilate never
bundles someone else's allowables, so where a number came from is a thing you assert and
the report records.

## A strength value also says how much of the population it covers

A citation on a strength carries a `basis`, and it is the difference between a number you
may use as a design allowable and one you may not:

| `basis` | Means |
| --- | --- |
| `typical` | a handbook mean — roughly half the material is weaker than it |
| `specification_minimum` | the floor the producer guarantees |
| `b_basis` | 90% of the population exceeds it, at 95% confidence |
| `a_basis` | 99% of the population exceeds it, at 95% confidence |
| `None` | **unclassified** — satisfies no requirement at all |

This distinction was always in the database. It was in *prose*, inside a source string
that either said "specified minimum" or did not, so nothing could read it and a reviewer
had to know which handbook table was a mean and which was a minimum. Now it is a field,
the provenance roll-up prints it (`ASM — AISI 4140 (typical)` against `ASTM A36 specified
minimum (specification minimum)`), and a check that needs a design allowable can demand
one:

```python
from anvilate.standards import AllowableBasis, require_basis

require_basis(record.yield_strength, AllowableBasis.SPECIFICATION_MINIMUM,
              material_id="AISI-4140", name="yield strength")
# InsufficientBasis: AISI-4140 yield strength is typical (Shigley ... Table A-21), and
#   this check requires at least specification_minimum ...
```

Every bundled strength is classified from **its own cited source**, not in bulk, and a
gate in the suite fails if a new record ships without one. Two records citing the same
book get different answers: Shigley's Table A-20 is titled "Deterministic ASTM *Minimum*
Tensile and Yield Strengths" and Table A-21 is "*Mean* Mechanical Properties of Some
Heat-Treated Steels". Of the 17 bundled materials, 8 carry specification minima and 9
carry typical values.

**Unclassified is not typical.** A record nobody has looked at fails a basis requirement
rather than passing as though somebody had — otherwise the requirement means nothing the
first time a record is added carelessly.

## A fatigue curve says the same thing, and one more

A fatigue curve carries its own version of the basis question, and it bites harder.
`CurveSurvival` says whether a curve is a **mean fit through the data** or a **design
curve** at a stated survival level — `95% survival`, or the mean-minus-two-standard-
deviations convention EN 1993-1-9 and IIW curves are drawn at. Reading the mean as the
design curve hands back exactly the margin that offset was there to provide — how much life
that is depends on the dataset's own scatter, which is why the curve says which it is
instead of quoting a factor. A mean curve asked for a design answer returns nothing:

```python
from anvilate.standards import CurveSurvival

record.allowable_stress_range(cycles=2_000_000, required_survival=CurveSurvival.P97_7)
# None — the curve is a mean fit
```

A record carries four things and cannot be built without any of them: the curve, the
survival level, **what it was measured on**, and where it came from. The third is the one
tables usually drop. A polished rotating-beam specimen and a welded joint are both "steel
fatigue data" and neither substitutes for the other, so geometry, loading mode,
environment, temperature and the stress ratio R are all required fields. R in particular:
the difference between an R = 0 and an R = −1 curve is the entire subject of mean-stress
correction, and a curve that does not say which it is cannot be corrected. A welded-joint
curve that is genuinely R-independent — residual stresses dominate — says so with a flag
rather than by inventing an R, and declaring both is refused, because guessing which one
was meant would put a mean-stress correction on a curve that already includes one.

And the curve declines outside the cycle range its method covers, rather than extrapolating.
The EN 1993-1-9 nominal-stress curve expressed in this schema returns nothing below 10,000
cycles, where the standard sends you to a strain-based assessment instead — while the bare
formula will happily evaluate there. **A power law run past the end of its method returns a
number that looks exactly like data.**

The dataset half is a license record too: `DatasetProvenance` requires a DOI or a URL,
because a fatigue curve nobody can retrieve is a number somebody typed.

## If a citation looks wrong

Report it. A wrong citation is worse than none, because it converts an unverified number
into a confidently-sourced one — the exact failure this library treats as the serious
kind.

## The basis is enforced, not just recorded

A strength value carries a **basis**: a typical value sits in the middle of the scatter —
roughly half the material is weaker than it — while a specification minimum is the floor the
producer guarantees. For 6061-T6 that is 276 MPa against 240.

Recording the distinction was half the job, and for one release it was the only half: every
pack check read `record.yield_strength.quantity` directly, so a check citing a published
clause consumed a mean strength silently, and nothing downstream could tell. **A check that
cites a clause now demands a design allowable**, because the clause is written on the
strength the material is sold with:

```python
screen_tension_member(member, required_safety_factor=1.67)   # AA-6061-T6
# [NOT_EVALUATED] tie gross yielding: not evaluated — AA-6061-T6 yield_strength is typical
#   (ASM Aerospace Metals — 6061-T6), and this check requires at least specification_minimum
```

Every check the screen would have produced is still named. A consumer looking for "gross
yielding" has to find it saying it could not run, rather than find nothing — which would be
its own kind of silence.

Nine of the seventeen bundled materials carry a specification minimum and screen exactly as
before. The other eight — mostly the aluminum alloys and the heat-treated steels whose
handbook tables are means — refuse until either the database gains a value on the right
basis, or the caller declares that this screen accepts a typical one:

```python
screen_tension_member(member, required_safety_factor=1.2, required_basis=AllowableBasis.TYPICAL)
# [PASS] tie gross yielding: safety factor 2.76 vs required minimum 1.20
#   [screened against a typical strength for AA-6061-T6, which the caller declared]
```

The declaration lands on **every entry the screen produced**, including the ones that passed.
An opt-in that produced an ordinary PASS would put back exactly the silence the gate removed.
