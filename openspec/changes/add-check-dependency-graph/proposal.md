# Change: Check dependency graph — a screen that consumes another screen's answer

## Why

The gauntlet runs tiers cheapest-first, but inside a tier every check is assumed
independent. Real physics is not. An internal heat source raises a sealed volume's
temperature; that temperature sets the material modulus; the modulus sets the mount
stiffness; the stiffness sets the fundamental frequency; the frequency sets the shock
amplification; the amplification sets the displacement that decides whether the design
survives. Six screens, one chain, and today nothing in the system says the fifth one reads
the fourth one's answer.

The consequences are the kind this project exists to refuse. A downstream check can run on
a stale upstream value and report a confident number. An upstream check can report "not
evaluated" while everything downstream of it reports a pass computed from a default. A
chain can be evaluated in an order that depends on dictionary iteration rather than on
dependency, so the same spec produces different answers on different runs. And a
conservatism applied upstream is invisible in the downstream result that inherited it.

Every multi-physics domain needs this — thermal-electronics, fluid power, precision
motion, opto-mechanics — so it belongs in the foundation rather than in the first module
that trips over it.

## What Changes

- `analysis-library` gains a declared-consumption contract: a check that reads another
  check's output declares it, so the dependency is data rather than an implementation
  detail buried in a call.
- `validation-gauntlet` evaluates checks in dependency order within a tier, refuses a
  cycle by naming its members, and records the realized evaluation order in the evidence
  bundle so a run is auditable and reproducible.
- **Status propagates downstream.** A check whose input came from an upstream check that
  did not evaluate reports "not evaluated" naming the upstream check — it MUST NOT fall
  back to a default and report a verdict.
- **Staleness propagates.** When an upstream result changes, everything downstream is
  recomputed or marked stale; a scorecard MUST NOT mix values from two different
  evaluations of the same chain.
- **Provenance and conservatism propagate.** A downstream result names the chain that
  produced its inputs, and inherits the upstream margin-ledger entries so the cumulative
  factor reflects the whole chain rather than the last link.

## Impact

- Affected specs: `analysis-library` (ADDED), `validation-gauntlet` (ADDED). Interacts
  with `margin-ledger` (inherited entries), `performance-budgets` (a contributor bound to
  a downstream check inherits the chain's status), `agent-repair-loop` (a repair must know
  what a change invalidates), and `calculation-report` (the derivation shows the chain).
- Affected code (when implemented): a declared-consumption annotation on checks, a
  topological evaluation pass, status and staleness propagation, and chain rendering.
- Explicitly out: automatic dependency inference from call graphs; iterative solution of
  circular couplings, which is a solver concern rather than a screening one; and any
  relaxation of the tier ordering, which continues to govern across tiers.
