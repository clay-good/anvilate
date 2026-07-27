# Change: Typed MBD callouts — finish, coating, and heat treat as data that drives checks

## Why

The in-flight `add-semantic-gdt-layer` change types the geometric half of model-based
definition. The other half — surface finish, coating, plating, heat treatment, and
process notes — remains free text everywhere in the industry, and it is the recognized
2026 MBD pain point: no shared ontology, so the same coating callout is expressed
differently in every tool.

For Anvilate these are not annotations; they are check inputs it currently ignores.
Surface finish sets the fatigue surface factor the shipped fatigue module already
parameterizes. Plating thickness changes an interference fit and thread engagement.
Heat-treat condition selects which row of the materials database is legitimate. A part
whose drawing says "black oxide, 32 Ra, heat treat to Rc 38" and whose calculations
silently assume a bare, ground, annealed part is exactly the silent-error class Anvilate
exists to eliminate.

There is also fresh open-standard momentum worth adopting rather than inventing: DMSC's
Model-Based Characteristics (MBC 1.0, ANSI-approved 2026, https://qifstandards.org/)
gives persistent characteristic identity — the identifier that lets a design callout, the
check that consumed it, and the inspection that verified it refer to the same thing
across revisions.

## What Changes

- `spec-ir` (ADDED): typed non-geometric callouts — surface finish, coating/plating,
  heat treatment, and structured process notes — each resolved against semantic tags,
  each carrying a persistent characteristic identifier stable across regeneration and
  revision.
- `validation-gauntlet` (ADDED): declared callouts that a check's method depends on SHALL
  be consumed by that check, with the consumed value and its effect stated; a callout
  that contradicts a check's assumption SHALL be surfaced rather than ignored.

## Impact

- Affected specs: `spec-ir` and `validation-gauntlet` (one ADDED requirement each).
  Complements `add-semantic-gdt-layer` (geometric callouts) and feeds
  `add-verification-test-plans` and `add-quality-evidence-interchange`, which both need
  stable characteristic identity; none of their requirements change.
- Affected code (when implemented): callout types on the spec, identifier assignment,
  and consumption in the fatigue, fit, and material-resolution paths.
- Out of scope: authoring a coating-process ontology, and finish/coating *selection*
  advice — Anvilate consumes declared callouts, it does not recommend them.
