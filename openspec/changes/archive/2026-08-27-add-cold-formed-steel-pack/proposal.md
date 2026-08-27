# Change: Cold-formed steel pack (AISI S100 Direct Strength Method)

## Why

Cold-formed steel design per AISI S100's Direct Strength Method is nearly empty in OSS:
the analysis half exists (pyCUFSM, a performant open-source finite-strip buckling port —
2025 paper with ClearCalcs deployment,
https://www.researchgate.net/publication/392162358), but no open design-check layer sits
on top; commercial tools (ClearCalcs, SkyCiv) prove the demand. DSM is Anvilate-shaped:
given elastic buckling values (local, distortional, global), member strength follows from
closed-form cited equations. Anvilate takes the buckling inputs as user-supplied or
pyCUFSM-computed values with provenance — the same interop posture as the member-force
change.

## What Changes

- `discipline-packs` gains a cold-formed steel pack requirement: DSM member-strength
  screens (compression and flexure: local, distortional, global limit states) per cited
  AISI S100 sections, consuming elastic buckling loads/moments as typed inputs with
  declared provenance (user-supplied or an external finite-strip tool).

## Impact

- Affected specs: `discipline-packs` (1 added requirement).
- Affected code (when implemented): new pack + analysis functions; optional pyCUFSM
  adapter mirrors the sectionproperties adapter pattern; worked-example anchors from
  published DSM design examples.
