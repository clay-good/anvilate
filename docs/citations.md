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
- **It is not a promise of coverage.** Every one of the 1,818 public analysis symbols now
  names a source — the debt in [`docs/api/uncited-symbols.txt`](api/uncited-symbols.txt) is
  paid, and the file stays as a ratchet so a new check cannot ship without one. Naming a
  source is not the same as having been checked against it: what a citation does and does
  not claim is the whole of this page.

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

## Every bundled table says what it may be redistributed under

A table bundled in the package travels with it, so whatever the data is licensed under, a
redistributor inherits. Each of the seventeen bundled datasets — the dimension tables, the
materials seed, the ISO 286 and ISO 2768 tolerance tables, the process-capability
estimates — declares a name, a version, the source it was read from, an SPDX licence
identifier, and the date it was retrieved. All seventeen are CC0-1.0 today: the *values*
are facts, and no source standard is redistributed.

A gate in the suite reads every one of them and fails the build on a licence that is not
redistributable inside an MIT package, a retrieval date that is not a date, or a missing
version — with a companion test that mutates a dataset each of those ways and requires the
gate to catch it. A dataset with no source at the dataset level (the materials table, whose
properties each cite a different publication) has to carry one on every record instead.

**The sweep is over what the wheel ships, not over where datasets live.** It used to walk
`standards/data` and `tolerance/data` — the two directories every dataset happens to sit in
today — so a `.csv` beside a module, a `.json` payload, or the allowables pack that
`expand-open-design-data` will add under `analysis/data` would have shipped with no licence
record and nothing would have noticed. Now every file inside the package that is not Python
must be a dataset with a redistributable licence or an exemption with a written reason, and
there is exactly one exemption: the agent skill, which is this project's own prose about its
own library. An adversary test writes an unlicensed data file into the installed package and
requires the sweep to see it.

Here they are, so that "what is in this package and under what terms" is a question you
answer by reading rather than by grepping. Every cell is read back out of the dataset
blocks themselves by `test_the_dataset_table_is_the_datasets_own_metadata`, so a table that
drifts from the files — a version bumped, a dataset added, a licence changed — fails the
build rather than going stale in a document.

| File | What it is | Version | Licence | Retrieved |
| --- | --- | --- | --- | --- |
| `standards/data/bearings.yaml` | ISO 15 deep-groove ball bearing boundary dimensions | 0.1.0 | CC0-1.0 | 2026-07-08 |
| `standards/data/cap_screws.yaml` | ISO 4762 (DIN 912) socket-head cap screw head dimensions | 0.1.0 | CC0-1.0 | 2026-07-08 |
| `standards/data/dowel_pins.yaml` | ISO 2338 parallel-pin dimensions | 0.1.0 | CC0-1.0 | 2026-07-08 |
| `standards/data/extrusions.yaml` | T-slot profile geometry (Bosch Rexroth / Misumi HFS common metric convention) | 0.1.0 | CC0-1.0 | 2026-07-08 |
| `standards/data/hex_bolts.yaml` | ISO 4014 / ISO 4017 hexagon-head bolt and screw head dimensions | 0.1.0 | CC0-1.0 | 2026-07-08 |
| `standards/data/hex_nuts.yaml` | ISO 4032 style-1 hexagon nut dimensions | 0.1.0 | CC0-1.0 | 2026-07-08 |
| `standards/data/materials.yaml` | per-record citations — every property cites its own publication | 0.1.0 | CC0-1.0 | 2026-07-08 |
| `standards/data/metric_clearance.yaml` | ISO 273 metric clearance holes | 0.1.0 | CC0-1.0 | 2026-07-08 |
| `standards/data/metric_thread.yaml` | ISO 261 / ISO 724 metric threads | 0.1.0 | CC0-1.0 | 2026-07-08 |
| `standards/data/nema_frames.yaml` | NEMA ICS 16 stepper frame mounting dimensions | 0.1.0 | CC0-1.0 | 2026-07-08 |
| `standards/data/pipe_schedules.yaml` | ASME B36.10M welded and seamless wrought steel pipe dimensions | 0.1.0 | CC0-1.0 | 2026-08-17 |
| `standards/data/washers.yaml` | ISO 7089 plain washer dimensions (normal series, 200 HV) | 0.1.0 | CC0-1.0 | 2026-07-08 |
| `tolerance/data/iso2768_angular.yaml` | ISO 2768-1 general tolerances (angular dimensions) | 0.1.0 | CC0-1.0 | 2026-07-08 |
| `tolerance/data/iso2768_linear.yaml` | ISO 2768-1 general tolerances (linear dimensions) | 0.1.0 | CC0-1.0 | 2026-07-08 |
| `tolerance/data/iso286_deviations.yaml` | ISO 286-1 fundamental deviations (shaft letters d/e/f/g, k, m/n/p, r/s <= 50 mm, u <= 18 mm) | 0.1.0 | CC0-1.0 | 2026-07-08 |
| `tolerance/data/iso286_grades.yaml` | ISO 286-1 standard tolerance grades (IT grades) | 0.1.0 | CC0-1.0 | 2026-07-08 |
| `tolerance/data/process_capability.yaml` | DFM screening estimates (typical finest achievable tolerances) | 0.1.0 | CC0-1.0 | 2026-07-08 |

Fetched data is not in that table, because none of it is in the package. One recipe ships
today — the MUSE benchmark's case index (CC BY 4.0, pinned to a commit rather than a
branch, since a leaderboard benchmark moves and a published score has to name the version
it was measured against) — and what ships is the URL and the digest, never the payload.

## Data this library may read and may not ship

Not every useful table is redistributable. A publisher's section database, a benchmark's
case archive, a registration-gated materials set: free to download, not free to bundle.
Those are fetched to your own machine once and read offline from then on, and
`anvilate.fetch` is that flow with three refusals in it.

**Consent is an argument, not a default.** A library cannot ask, so it does not guess: a
fetch happens only when the caller states that the user agreed, and otherwise the refusal
names the URL, the source and the licence — which is what somebody needs in order to be
asked.

**A payload that is not its digest is not the dataset.** The checksum is verified before
anything is cached and again on every read, so a truncated download, a mirror serving
something else and a file edited in the cache are all refused rather than parsed. A failed
fetch leaves nothing behind.

**The cache says where its contents came from.** Beside each payload sits a provenance
record — the URL, the digest, the licence, whether it is redistributable at all, and the
retrieval date. The date is the caller's to state: nothing in the package reads the clock,
because an evidence bundle's digest has to rebuild identically. A payload whose provenance
sidecar is missing is refused too; data whose origin the cache cannot state is data nothing
should cite.

**An attribution licence is a condition, not a formality.** CC BY 4.0 grants the use in
exchange for the credit, so the flow that fetches the data is the one that can state it:
`attribution()` turns a provenance record into the credit line — source, URL, licence,
retrieval date — and says outright when a source is one this project may read and not
ship. Releases carry the recipe and the digest, never the payload.

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
member = TensionMember(
    name="tie", material="AA-6061-T6", load=Quantity.parse("50 kN"),
    gross_area=Quantity.parse("500 mm**2"), net_area=Quantity.parse("450 mm**2"),
)
screen_tension_member(member, required_safety_factor=1.67)
# [NOT_EVALUATED] tie gross yielding: not evaluated — AA-6061-T6 yield_strength is typical
#   (ASM Aerospace Metals — 6061-T6), and this check requires at least specification_minimum
```

Every check the screen would have produced is still named. A consumer looking for "gross
yielding" has to find it saying it could not run, rather than find nothing — which would be
its own kind of silence.

Eight of the seventeen bundled materials carry a specification minimum and screen exactly as
before. The other nine — five of the six aluminium alloys, both heat-treated steels, the
bearing bronze and the titanium, whose handbook tables are means — refuse until either the
database gains a value on the right basis, or the caller declares that this screen accepts a
typical one:

```python
screen_tension_member(member, required_safety_factor=1.2, required_basis=AllowableBasis.TYPICAL)
# [PASS] tie gross yielding: safety factor 2.76 vs required minimum 1.20
#   [screened against a typical strength for AA-6061-T6, which the caller declared]
```

The declaration lands on **every entry the screen produced**, including the ones that passed.
An opt-in that produced an ordinary PASS would put back exactly the silence the gate removed.
