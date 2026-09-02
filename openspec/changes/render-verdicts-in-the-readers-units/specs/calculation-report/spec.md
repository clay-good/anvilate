# Calculation Report Specification (delta)

## MODIFIED Requirements

### Requirement: Unit-system fidelity in derivations

Derivations SHALL render every value in the project's declared unit system at the code-conventional precision defined by the units capability, while the calc record carries full-precision canonical values; a substituted value MUST never appear without its unit.

The same SHALL hold for the **verdict line** beside them. A check that judges one quantity against another SHALL carry both quantities, so the sentence stating the comparison is rendered by the document rather than written by the screen: a screen does not know what system its result will be read in, and a sentence baked at screening time states the comparison in whatever units the check happened to compute in. Nothing in a document may carry a unit from a system the document did not declare.

A display unit a check prefers SHALL yield to a declared system, except where the preference is arithmetic rather than taste — a unit-per-dimension table cannot tell a section modulus from a room's volume, and a symbol it would mangle keeps its unit under every system.

#### Scenario: US project derivation

- **WHEN** a `units: US` project renders a bearing-stress derivation
- **THEN** substituted values appear in kip and inch units and the result in ksi at conventional precision, with full-precision values in the calc record

#### Scenario: The verdict follows the derivation

- **WHEN** a report declaring US-customary units prints a deflection check
- **THEN** the verdict states the deflection and its limit in inches, in the same system as the worked derivation above it

#### Scenario: A comparison between unlike quantities is refused

- **WHEN** a check declares a measured value and a limit of a different dimension
- **THEN** the entry is refused, because a length judged against a frequency is not a comparison and a rendered sentence would give it the appearance of one
