# Change: Geometric DFM rules — read the built solid the way a shop quoting it would

## Why

The `validation-gauntlet` spec promises a T2 tier of manufacturability rules over the
tagged solid. What ships today is one screen: whether a process can hold a tolerance.
Everything a shop sends back with a quote is missing. An internal corner sharper than any
end mill. A hole twelve diameters deep. A rib as thick as the wall it sits on, which
leaves a sink mark on a class-A surface. A flange too close to a bend to form. A wall the
die-caster cannot fill.

These rules are the highest-volume rework in Tier 1 and Tier 2 automotive suppliers, in
consumer products and in machine shops. They need no solver: each is a measurement of
the built solid against a ratio in a process profile. Commercial DFM tools sell exactly
this as an add-on to CAD. An open rule set, cited rule by rule, that runs on every build
the agent makes, is a large gain for little code.

## What Changes

| Process | Rules (first set) |
| --- | --- |
| CNC milling and turning | Internal corner radius against the smallest declared tool; hole depth to diameter; thin walls and tall thin bosses; undercuts the declared setups cannot reach; threads deeper than tap reach |
| Sheet metal | Bend radius against thickness and material; hole and slot to bend and to edge; flange minimum length; bend relief; features across a bend line |
| Injection molding | Wall thickness and its uniformity; draft per face against texture; rib and boss proportions to the nominal wall; sharp internal corners; undercuts in the pull direction |
| Die casting | Draft, wall uniformity, isolated heavy sections (shrinkage hotspots) |
| Additive (FDM, SLS, LPBF) | Overhang angle against the build direction; minimum wall and hole; trapped powder or unsupported bridges |
| Weldments | Weld access by torch angle; distortion-prone long single-side welds |

- Every rule cites its source or is labeled a practice-based default, and its threshold
  lives in a process profile the user can override with their shop's numbers and a source.
- A finding names the face or edge by tag, the measured value, the limit, and the
  repair lever (radius, draft, wall), in the form the repair loop consumes.
- Cost estimation gains sheet metal, injection molding (tooling plus piece price,
  screening grade) and die casting, so a DFM change shows its cost effect.

## Impact

- Deltas: `validation-gauntlet` (ADDED), `cost-estimation` (ADDED).
- Builds on the tagged B-Rep and the existing process-capability table; uses
  `add-assembly-feasibility`'s tool envelopes for reach.
- Explicitly out: mold-flow simulation, forming simulation, toolpath generation, and any
  rule whose only source is a licensed handbook table (thresholds from such sources are
  entered by the user with a citation, never bundled).
