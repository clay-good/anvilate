# Tasks: Physical-domain modules

## 1. Contract

- [x] 1.1 Module manifest type: id, namespace, version, unit default, standards +
      editions, required material property sets, tiers touched, module dependencies — exact
      and prefix-overlapping namespaces are refused; document-driven module entries carry a
      stable namespaced `check_id` resolved through the limit-state registry while their
      instance-specific display names remain unchanged
- [x] 1.2 Declared screening coverage type: what the module claims it can screen
- [x] 1.3 Deprecation state on a manifest, and what a deprecated module renders

## 2. Registry

- [x] 2.1 Manifests for the nine shipped packs, asserted against what each already exposes
- [x] 2.2 Loader honoring enable/disable, lazy import, and declared dependencies
- [x] 2.3 Duplicate-limit-state detection across loaded modules — `anvilate.limit_states`:
      a registry id per limit state, with the registry, composition and emission gates in
      docs/discipline-modules.md

## 3. Gates

- [x] 3.1 CI gate: manifest completeness, enumerating missing items on failure
- [x] 3.2 CI gate: per-module exercise floor as a counted fraction with a population size
      assertion, so an empty or shrunken module fails rather than passes
- [x] 3.3 CI gate: a module's declared standards resolve in the standards database, both
      directions — every declared standard is used, every used standard is declared

## 4. Third-party modules

- [x] 4.1 Opt-in loading of out-of-tree modules under the existing sandbox — was BLOCKED on
      there being no sandbox. Built 2026-10-09 at the user's request: `anvilate.thirdparty`
      enables a module only by path (`--module` on check/diff/export/build/view, or at
      `anvilate-mcp` launch; never discovered, never named by a document or tool call), and
      runs each call in `_sandbox_child.py`, a separate isolated process with the
      sandbox-security constraints: no network, file access limited to a scratch directory
      (plus reading the module and the Python installation), CPU, memory, file-size and
      descriptor limits, and a wall-clock timeout. A violation ends the call and is logged as
      the check's not-evaluated reason, even if the module catches it. The boundary is an
      audit hook, stated in SECURITY.md as stopping mistakes and ordinary misbehaviour and
      not hostile native code, which is what 4.2 is for. A module may add an element type,
      never replace one. Tests: tests/test_thirdparty.py, which attacks each rule.
- [x] 4.2 Unverified-origin marking that survives into the scorecard and evidence bundle —
      every entry a third-party module contributes carries `origin` (module, version, path,
      SHA-256 of the source that ran; scorecard 1.14.0). `check` prints it and counts it,
      the report and part sheet print it, the evidence bundle embeds it, and
      `authorize_export` never counts such a pass as validated: it exports only watermarked.

## 5. Docs

- [x] 5.1 "Write a module" page: the manifest, the composition rule, the coverage floor
- [x] 5.2 Update `discipline-packs` docs to point domain specs at their own capability
