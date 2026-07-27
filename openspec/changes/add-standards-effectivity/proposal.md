# Change: Standards effectivity — code edition as a first-class, diffable parameter

## Why

Every check Anvilate ships cites a clause, but a clause without an edition is ambiguous:
AISC 360-16 and -22, ACI 318-14 and -19, and the biennial ASME BPVC editions all coexist
in active practice, and jurisdictions adopt them on their own schedules. Commercial tools
treat edition as a dropdown; the closest OSS prior art, fib's `structuralcodes`, ships
Eurocode 2 (2004) and (2023) as parallel namespaces
(https://github.com/fib-international/structuralcodes) — a versioning convention, not
effectivity semantics. Nobody does jurisdiction-aware resolution or edition-diff
reporting.

For Anvilate the cost is low and the payoff compounds: the evidence bundle's entire claim
is "these numbers came from these clauses," and an unversioned clause weakens it. The
unclaimed differentiator is edition-diff awareness — telling a user that the equation
governing their check changed between editions and what the result is under each, seeded
from publishers' own comparison documents (e.g. AISC's 2022-to-2016 comparison,
https://www.aisc.org/publications/steel-standards/aisc-360/comparison/).

## What Changes

- New capability spec `standards-effectivity`: edition is a required field on every
  citation; a spec declares a design basis pinning editions per standard; mixing editions
  within one evidence bundle requires an explicit recorded waiver; superseded editions
  are usable but labeled; and where a check's governing provision differs across
  supported editions, the system reports the difference and can evaluate under both.
- An optional, offline, staleness-dated jurisdiction table may map a jurisdiction to the
  editions its adopted building code references — advisory only, never authoritative.

## Impact

- Affected specs: new `standards-effectivity`. Interacts with `standards-data` (which
  already versions its databases), `validation-gauntlet` (citation contents), and
  `add-calculation-report` (the report header already lists code editions) — none of
  their existing requirements change.
- Affected code (when implemented): citation type gains edition fields; a design-basis
  resolver; an edition-delta registry populated per supported check.
- Out of scope: shipping the standards' text, and any claim of legal code compliance.
