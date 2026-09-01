# Tasks: Derivation coverage ratchet

## 1. Decide

- [ ] 1.1 What identifies a check, given `ScorecardEntry.name` is per-part prose and the
      clause reference is shared by more than one check. **Blocking**: the requirement's
      scenario is "CI fails **naming the check**".
- [ ] 1.2 How the gate harvests — a session-wide patch in `conftest.py`, ordering-sensitive,
      or a second suite run in a subprocess costing about 90 seconds of CI.

## 2. The registry (follows 1.1)

- [ ] 2.1 Two categories, not one: a **lookup** has no formula to render and is done; a
      **debt** is a formula whose derivation is unwritten. Filing a debt as a lookup is the
      failure this registry exists to prevent.
- [ ] 2.2 Classify the 57 clauses that carry no derivation today. One at a time,
      against the standard, because there is no pattern that separates the two categories.

## 3. The gate (follows 2)

- [ ] 3.1 Report the ratio. Today it is 18/75.
- [ ] 3.2 Fail on a clause in neither list — which is the requirement's own scenario, and
      the only part of this that a newly added check actually meets.
- [ ] 3.3 Ratchet the debt list downward-only: a clause may leave it by acquiring a
      derivation, never by being reclassified as a lookup without the reason changing too.

## Status

Not started. Measured 2026-09-01 at 18/75 and written up rather than
half-built: a ratchet seeded with 57 guesses would look like enforcement and
enforce a list nobody read a standard for.
