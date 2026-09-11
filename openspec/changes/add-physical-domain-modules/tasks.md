# Tasks: Physical-domain modules

## 1. Contract

- [ ] 1.1 Module manifest type: id, namespace, version, unit default, standards +
      editions, required material property sets, tiers touched, module dependencies
- [ ] 1.2 Declared screening coverage type: what the module claims it can screen
- [ ] 1.3 Deprecation state on a manifest, and what a deprecated module renders

## 2. Registry

- [ ] 2.1 Manifests for the nine shipped packs, asserted against what each already exposes
- [ ] 2.2 Loader honoring enable/disable, lazy import, and declared dependencies
- [ ] 2.3 Duplicate-limit-state detection across loaded modules

## 3. Gates

- [ ] 3.1 CI gate: manifest completeness, enumerating missing items on failure
- [ ] 3.2 CI gate: per-module exercise floor as a counted fraction with a population size
      assertion, so an empty or shrunken module fails rather than passes
- [ ] 3.3 CI gate: a module's declared standards resolve in the standards database, both
      directions — every declared standard is used, every used standard is declared

## 4. Third-party modules

- [ ] 4.1 Opt-in loading of out-of-tree modules under the existing sandbox
- [ ] 4.2 Unverified-origin marking that survives into the scorecard and evidence bundle

## 5. Docs

- [ ] 5.1 "Write a module" page: the manifest, the composition rule, the coverage floor
- [ ] 5.2 Update `discipline-packs` docs to point domain specs at their own capability
