# Change: Declaration completeness — make the rigor drivable

## Why

Every hardening pass on this project adds a declaration. Declare the environment kind.
Declare the damping. Declare the orientation. Declare the constraint topology, the keepout
anchor, the combination rule, the contributor basis, the fill condition, the heat path.
Each one is individually right — it is how the system refuses to invent a value — and the
cumulative effect is a tool that answers a first-time user with forty "not evaluated"
entries and no obvious next move.

That is the friction this product exists to remove, reintroduced from the other side. An
engineer who abandons Anvilate at the wall of red gets no screening at all, which is
strictly worse than the imperfect spreadsheet they were using. Rigor that nobody can drive
is not rigor.

The fix is not to weaken any refusal. It is to make the refusals navigable: one
consolidated list of what the build needs, ordered by what unblocks the most work; named,
cited, versioned **profiles** that supply a coherent set of declarations at once with
their provenance intact; and a declared **screening depth**, so a card can distinguish "I
chose not to screen that yet" from "I forgot," and an early-concept run is a short honest
card rather than a long red one.

## What Changes

- New capability spec `declaration-completeness`: a single consolidated report of every
  declaration the build needs, each naming the screens it unblocks, ordered by how much it
  unblocks, with ties reported rather than broken arbitrarily.
- **Profiles**: a named, versioned, cited bundle of declarations — an environment profile,
  a material-handling profile, a shop-practice profile — that supplies many declarations
  at once. Every profile-sourced value is marked as such wherever it appears, is
  individually overridable, and never silently governs a verdict.
- **Screening depth**: a spec may declare how deep it wants to be screened. Screens
  outside the declared depth report "out of declared depth," which is visibly distinct from
  "not evaluated," and the card states both counts so the distinction cannot be lost.
- Raising the depth is a one-action change that re-reports what it newly requires, so
  deepening a screen is an obvious next step rather than an archaeology exercise.

## Impact

- Affected specs: new `declaration-completeness`; `validation-gauntlet` (ADDED).
  Interacts with `intent-compilation` (the compiler already asks one question at a time),
  `onboarding`, `workbench-ui`, `standards-data` (profiles are provenance-bearing records),
  and every change that adds a required declaration.
- Affected code (when implemented): a needs-collector over the scorecard, profile records
  and binding, depth gating, and rendering.
- Explicitly out: inferring declarations the user did not make; profiles that carry
  engineering values a standard does not support; and any depth setting that suppresses a
  refusal without saying so on the card.
