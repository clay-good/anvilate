# Change: Failure-mode coverage — answer the question nobody asked

## Why

Anvilate answers every question the document asks. The expensive failures are the ones
nobody asked.

A scorecard today can report a clean pass on twelve checks while the part goes on to fail
qualification by fogging, by loosening, by galvanic corrosion at a dissimilar-metal joint,
by fretting at an interface nobody declared as one. Not one of those is a bug in a screen.
Each is a failure mode that no screen addressed and no entry mentioned, so the card was
silent about it — and a silent card reads as a clean one.

The economics are the whole argument for fixing this. Roughly 80% of a product's cost is
committed during concept, and the cost of correcting a defect rises by about an order of
magnitude at each stage it survives — the same fix that costs a parameter change in design
costs a tooling change in production and a recall in the field. A screening tool's value
is not the checks it runs; it is the number of stages it pulls a discovery *earlier*. That
means the tool must be able to say what it did not check, by name, from a catalog rather
than from the user's memory.

`verification-planning` already reports coverage honestly — but of *checks*. This reports
coverage of *failure modes*, including the ones with no check at all, which is the only
view in which an unaddressed mode is visible.

## What Changes

- New capability spec `failure-mode-coverage`: a cited, versioned catalog of failure modes
  keyed by element class, material pairing, interface type, and declared environment;
  every mode applicable to a spec resolves to screened, verification-only, or
  **unaddressed**, and unaddressed modes are enumerated by name.
- Coverage is reported as a count and a population size, never a bare percentage, and the
  unaddressed set is always listed — a coverage figure with no denominator and no names is
  the kind of number that reassures without informing.
- Each mode carries the **stage at which it would otherwise be discovered** — design,
  assembly, qualification, or field — so the report shows which unaddressed modes are the
  expensive ones to leave. This is a discovery-stage attribute, explicitly not a severity
  ranking.
- Modules contribute the failure modes of their domain under the module contract, so the
  catalog grows with the system instead of being a fixed list.
- A card with unaddressed applicable modes MUST NOT present itself as a complete answer.

## Impact

- Affected specs: new `failure-mode-coverage`; `validation-gauntlet` (ADDED);
  `discipline-packs` (ADDED). Interacts with `verification-planning` (a
  verification-only mode emits a test item), `declaration-completeness` (an unaddressed
  mode is often one declaration away from being screened), `responsible-charge-review`,
  and `benchmarking` (an escaped defect adds a catalog entry as well as a regression).
- Affected code (when implemented): the catalog as provenance-bearing data, an
  applicability resolver, the coverage reporter, and per-module contributions.
- Explicitly out: risk-priority scoring, probability or severity estimation, automatic
  mitigation generation, and any claim that the catalog is exhaustive — it is a floor that
  rises, and the spec says so.
