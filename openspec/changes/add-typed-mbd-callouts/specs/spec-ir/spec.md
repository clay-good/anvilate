# Spec IR Specification (delta)

## ADDED Requirements

### Requirement: Typed non-geometric callouts with persistent identity

The Spec IR SHALL support typed non-geometric callouts — at minimum surface finish
(roughness value, parameter, and production method), coating or plating (specification,
class or type, and thickness range), heat treatment (specification and resulting
condition or hardness range), and structured process notes with a category and typed
parameters — each scoped to the whole part or resolved against semantic tags, and each
rejected with a named field when its specification reference or units are invalid. Every
callout SHALL carry a persistent characteristic identifier that survives geometry
regeneration and spec revision, so a callout, the checks that consume it, and any
inspection or test that verifies it refer to the same characteristic over time.

#### Scenario: Finish scoped to a face

- **WHEN** a finish callout is applied to the `bearing_bore` tag
- **THEN** it resolves against the semantic tag graph, stores its roughness parameter and
  value with units, and is rejected naming the tag if that tag does not exist

#### Scenario: Identity survives regeneration

- **WHEN** geometry is regenerated from scratch and the spec is revised elsewhere
- **THEN** each existing callout keeps its characteristic identifier, and a diff can
  report which characteristics changed, were added, or were removed

#### Scenario: Free text stays free text

- **WHEN** a note carries no recognized category or typed parameters
- **THEN** it is stored as an unstructured note, clearly distinguished from typed
  callouts, and no check may consume it
