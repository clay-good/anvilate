# Change: Interface contracts — the connection list a product is checked against

## Why

Most of what goes wrong in a product goes wrong where two items meet: a bolt pattern one
supplier moved, a shaft 0.5 mm over the bore it goes in, a connector with no room to mate,
a motor flange drawn to last year's datasheet. Combinations already check a meeting once
two tagged features are named in a mate. What they cannot do is say what each item
*offers* to the rest of the product before anyone mates it, or notice an interface nobody
connected.

Electronics design solved the same problem decades ago, and the pattern carries across
almost unchanged:

| Electronics | Mechanical equivalent |
| --- | --- |
| A pin has a type (power in, output, passive) | An interface has a kind (bolt pattern, shaft, bore, mounting face, rail, connector) |
| A netlist says which pins connect, separate from layout | A connection list says which interfaces meet, separate from where things end up |
| ERC flags an unconnected input or two outputs driving one net | Product rule check flags an unconnected mounting interface or a shaft offered to a bolt pattern |
| A pin left open on purpose is marked no-connect | An interface left open on purpose is marked open, with a reason |
| A part's library entry brings its own checks | An interface kind brings its own checks: a bolt pattern brings engagement and bearing, a bore brings its fit |

Mechanical engineers already keep this record by hand, as an interface control document,
in a spreadsheet that drifts from the model. Making it the thing the model is built from
removes the drift.

## What Changes

| Area | Change |
| --- | --- |
| Interfaces on items | Every part, combination, product, component and placeholder may publish named, typed interfaces: a kind, a frame (origin, normal, spin reference), and the kind's parameters (pattern, diameter, fit, rating). |
| Connection list | A product may connect interfaces by name (`base.motor_mount ~ motor.flange`) instead of naming features in mates. Placement is derived from the connection; the mate vocabulary is unchanged underneath. |
| Compatibility | A table says which kinds can meet and what each pairing checks. A pairing the table does not allow is refused before geometry is built. |
| Checks owned by the kind | Each pairing brings the checks the combination layer already runs (pattern agreement, fit, engagement, bolted joint) plus the kind's own. |
| Product rule check | Every interface is connected, marked open with a reason, or reported. An interface with two partners where the kind allows one is reported. |
| Interface table | Every product build writes an interface control table: each connection with both sides' parameters, the owner, the checks and their verdicts. |

## Impact

- New capability: `interface-contracts`. Delta: `assembly-robotics` (ADDED).
- Builds on `add-product-structure` (items and paths) and `add-part-combinations` (mates
  and joint checks, reused, not rewritten). Generalizes the existing `spec-ir` "Spec
  composition via interface imports" requirement from one imported pattern to every
  interface an item offers.
- Explicitly out: electrical, fluid and data connectivity beyond the mechanical envelope
  a connector or port needs (its keepout); automatic inference of interfaces from
  imported geometry (they are declared, or read from a component's record).
