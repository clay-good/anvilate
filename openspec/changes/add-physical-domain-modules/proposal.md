# Change: Physical-domain modules — turn the pack list into a module contract

## Why

Anvilate's foundation is domain-neutral. Units, the Spec IR, the scorecard, the citation
doctrine, the no-silent-green rule, and the evidence bundle know nothing about steel,
timber, or piping — which is exactly why nine disciplines already sit on top of them. The
same foundation supports physical-design domains well beyond the ones shipped:
opto-mechanical assemblies, thermal-electronics enclosures, fluid power, precision motion.

The blocker is spec shape, not capability. `discipline-packs` today carries one thin
"Discipline pack contract" requirement and then eight requirements that each enumerate a
specific pack. Adding a domain therefore means editing the shared spec, and the contract
itself never had to answer the questions a tenth domain asks: what does a module declare
about itself, what may it depend on, what happens when two modules implement the same
limit state, how is it versioned, and what stops a module from shipping checks nothing
exercises.

This change promotes the contract and leaves the shipped packs alone. A new domain becomes
a manifest plus its own capability spec, not a rewrite of a shared one.

## What Changes

- **MODIFIED** the pack contract into a **module manifest**: stable id and reserved check
  namespace, semantic version, declared unit default, declared standards with editions,
  declared material property sets required, declared pipeline tiers touched, declared
  dependencies on other modules, sample specs, docs, and golden tests.
- **ADDED** composition over duplication: a module MUST reuse an existing screen where one
  exists and MUST NOT ship a second, conflicting implementation of the same limit state —
  generalizing the rule the lifting-device pack already follows for lug checks.
- **ADDED** declared screening coverage: a module states which declarations it can screen,
  and anything outside that set reports "not evaluated" naming the module, wiring modules
  into no-silent-green rather than letting them fall silent.
- **ADDED** module versioning, deprecation, and the requirement that new domains are
  specified in their **own capability spec**, not appended to `discipline-packs`.
- **ADDED** a per-module exercise floor in CI: every check a module publishes must be
  reached by at least one test and one runnable example, and the floor is a counted
  fraction so a module cannot shrink its way to green.
- **ADDED** third-party module discovery with no implicit trust: out-of-tree modules load
  only on explicit opt-in, run under the existing sandbox, and are marked as
  unverified-origin in every scorecard and evidence bundle they touch.

- **ADDED** limit states identified by shared registry id, so composition and duplicate
  detection key on the concept rather than on function names or citation text.
- **ADDED** namespace and module-id collisions refused at load with no last-wins
  resolution, the enabled module set as part of the reproducibility contract, and a
  module unit default that never overrides a spec's declared system.

## Impact

- Affected specs: `discipline-packs` (MODIFIED + ADDED). Interacts with
  `validation-gauntlet` (no-silent-green), `sandbox-security` (third-party loading),
  `benchmarking` (coverage floor), and `documentation` — none change.
- Affected code (when implemented): the `packs` registry gains a manifest type and a
  loader; existing packs gain manifests; CI gains the exercise-floor gate.
- Explicitly out: rewriting or removing any shipped pack's requirements; a plugin
  marketplace; remote module fetching.
