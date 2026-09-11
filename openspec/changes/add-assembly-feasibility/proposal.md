# Change: Assembly feasibility — can a person actually build this

## Why

T2 already screens whether a *cutter* can reach a feature. Nothing screens whether a
*hand, a driver, or a torque wrench* can. Those are different questions with the same
consequence, and the second one is discovered later and more expensively: on the bench,
with the parts already made.

The cases are mundane and constant. A cap screw whose head clears but whose driver does
not. A wrench with no room to swing through a useful arc. An adjustment screw that is
perfectly accessible until the cover goes on, at which point the assembly can never be
aligned again. A part that can only be inserted in a direction another part already
occupies, so the assembly has no valid order at all. A bonded joint that must cure while
something holds it, with nowhere for the fixture to hold. None of these is exotic, all of
them are geometric, and every one of them is cheaper to catch as a parameter change than
as a rework cycle.

Opto-mechanics makes this sharper than most. Sealed housings with internal adjustments are
the normal case, alignment must happen *after* enough of the assembly exists to align
against, and the seal that makes the instrument survivable is the same seal that makes
everything inside it unreachable. A tool that screens the optics beautifully and cannot
say whether the adjustment can be turned with the cover on has not finished the job.

## What Changes

- New capability spec `assembly-feasibility`: tool access screened as a declared tool
  envelope swept along a declared approach, per fastener and per adjustment; wrench swing
  arc against the available clearance; and assembly-state awareness, so access is
  evaluated in the state the operation actually happens in, not on the bare part.
- **Assembly order**: parts declare insertion direction and the features they occupy, and
  the system reports whether a valid order exists — a part with no insertion direction
  available after its neighbours is a finding naming the blocking parts.
- **Serviceability and alignment access**: a feature declared adjustable or serviceable
  must remain reachable in the assembly state it is used in, and a sealed enclosure that
  makes an adjustment unreachable after closure is a finding, not a silence.
- **Inspectability**: a dimension carrying a tolerance that cannot be measured in any
  achievable assembly state is reported, because a tolerance nobody can verify is a
  drawing note rather than a control.
- `spec-ir` gains the declarations these screens read: tool envelopes, approach
  directions, assembly states, and per-feature access requirements.

## Impact

- Affected specs: new `assembly-feasibility`; `spec-ir` (ADDED). Interacts with
  `keepout-envelopes` (a tool sweep is a keepout, reusing the intrusion check rather than
  inventing a second one), `validation-gauntlet` (a T2-class screen), `assembly-robotics`
  (typed assemblies and joints already exist), `tolerance-management` (inspectability),
  and `failure-mode-coverage` (these are assembly-stage discovery modes).
- Affected code (when implemented): tool-envelope archetypes, swept-access generation
  composed from the keepout mechanism, an order solver over declared insertion
  directions, and assembly-state evaluation.
- Explicitly out: full assembly-path planning through obstacles; ergonomic and
  human-factors modelling; robotic assembly sequencing; and automatic inference of
  insertion directions from geometry.
