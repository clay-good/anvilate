# Change: Keepout envelopes — space that must stay empty, as a first-class declaration

## Why

Every pattern in the pattern library adds material. Every geometry check asks about the
material that is there. But a large share of what actually constrains a design is about
space that must remain *empty*: a cable's bend radius, the volume a connector needs to
mate, the reach a hand or a tool needs for service, the swept volume of a moving part, the
airflow corridor over a heat sink, the cone of light between two lenses.

Today a spec can declare an overall bounding envelope and nothing finer. So these
constraints live in the engineer's head, get violated by a rib added to fix a deflection
failure, and are discovered in assembly. That is precisely the class of error a screening
tool should catch for free — it is a solid-solid intersection, computable at T0, needing
no mesh and no solver.

This is foundation work rather than module work because every domain has one. The
opto-mechanical module needs the beam cone and would otherwise invent a private version of
a primitive that cable routing, service access, and robot sweep all need too.

## What Changes

- `spec-ir` gains a typed **keepout declaration**: a semantic tag, a generating rule, a
  declared clearance margin, the reason it exists, and its owner (user or module).
- `geometry-generation` generates keepout bodies through the same pattern-constrained,
  sandboxed, semantically tagged mechanism as material geometry — a keepout is geometry,
  not an annotation, and is never produced by freestyle code.
- `validation-gauntlet` gains a T0 **intrusion check**: any material intersecting a
  keepout fails, naming the intruding tagged feature and quantifying the intruded volume
  and the worst penetration depth; intrusion into the clearance margin but not the
  protected core is a warning, not a pass.
- `artifact-export` keeps keepouts on their own layer or body, labeled non-manufacturing,
  so a downstream reader can see the constraint and can never machine it by accident.

- **ADDED** keepouts anchor to a semantic tag and move with it — an unanchored envelope
  silently stops protecting the right region the moment a change moves the feature — plus
  a clean result that states how many keepouts it screened and the smallest clearance it
  found, and an explicit nominal-geometry basis with a warning when clearance is smaller
  than the tolerances bearing on it.

## Impact

- Affected specs: `spec-ir` (ADDED), `geometry-generation` (ADDED),
  `validation-gauntlet` (ADDED), `artifact-export` (ADDED). Interacts with
  `assembly-robotics` (swept volumes are keepouts), `drawing-generation`, and
  `agent-repair-loop` (an intrusion is a repairable failure with an obvious lever).
- Affected code (when implemented): keepout archetypes in the pattern library, a boolean
  intrusion check, an export layer convention, and repair hints.
- Explicitly out: automatic keepout inference from a prompt; continuous collision
  detection over a trajectory (a swept volume is declared, then checked statically);
  tolerance-aware intrusion, which follows the tolerance model rather than leading it.
