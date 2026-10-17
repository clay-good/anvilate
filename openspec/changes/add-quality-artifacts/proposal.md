# Change: Quality artifacts — fill the forms the industry already runs on, from evidence already computed

## Why

In automotive, aerospace and medical work, the design is not done when the part passes.
It is done when its paperwork passes. Each industry runs on a few artifacts with the same
bones, and engineers fill them by hand from the analysis they already did:

| Industry | Artifacts |
| --- | --- |
| Automotive | DFMEA, special characteristics, design verification plan and report (DVP&R), control plan, PPAP |
| Aerospace | Verification cross-reference matrix, first article inspection (FAI) with every characteristic numbered, configuration records |
| Medical devices | Design controls traceability (needs → requirements → design → verification), ISO 14971 risk file, design history file |
| Industrial machinery | ISO 12100 risk assessment, which matters more now that the EU Machinery Regulation applies from 2027-01-20 |

Anvilate already holds most of the content: the failure modes a design must address, the
checks that prevent each, the verification archetype that detects each, the toleranced
characteristics, and the trace from requirement to check. What it lacks is the shape of
the forms. That is most of what an engineer retypes.

The handbooks behind these forms are copyrighted, and their rating tables and
action-priority matrices are licensed. This change uses only the open structure (field
names, the links between rows), its own published rating scales, and the user's own
tables when they load them. It never reproduces a licensed table.

## What Changes

| Area | Change |
| --- | --- |
| Design FMEA | Rows generated from the design: function, failure mode, effect, cause, prevention controls (the card's checks), detection controls (the verification plan). Severity is the user's. Occurrence and detection are rated on Anvilate's published scales, or on the user's loaded tables. |
| Special characteristics | Any dimension, tolerance or property can be marked critical or significant, with the symbol the user's customer uses. The mark flows to drawings, QIF, the inspection plan and the control-plan seed. |
| Verification plan as DVP&R | The existing verification plan exports with the columns a DVP&R has: requirement, test, acceptance criterion, sample size, timing, owner, result. |
| Characteristic accountability | Every characteristic on a drawing gets a balloon number that is stable across revisions, plus a table to record measured results, shaped for first-article inspection. |
| Risk files | Hazard records in the open structure shared by ISO 14971 and ISO 12100: hazard, hazardous situation, harm, risk control, verification. A control that is an Anvilate check links to its entry. |
| Traceability | Requirement → item → check → verification → evidence, exported as CSV and as ReqIF (the open requirements-exchange format) for requirements tools. |

## Impact

- New capability: `quality-artifacts`. Deltas: `verification-planning` (ADDED),
  `drawing-generation` (ADDED).
- Builds on `verification-planning`, `add-failure-mode-coverage`, `tolerance-management`,
  `add-semantic-gdt-layer`, the QIF export, `add-requirements-doc-ingestion`, and
  `add-product-structure`.
- Explicitly out:
  - Process FMEA beyond the seed the design hands to manufacturing.
  - PPAP submission.
  - Approval workflows and electronic signatures. These belong to the user's QMS.
  - Any claim that an artifact satisfies a regulation. Anvilate fills forms; people and
    auditors decide compliance.
