# Change: Person confirmation — the decisions that must be a person's reach the person, not the agent

## Why

Four things in Anvilate are supposed to be decided by a human being, by design:

| Decision | Where the rule lives |
| --- | --- |
| Confirming a value the agent read off a picture, a PDF or a sketch | `add-agent-context-intake`: a draft is not load-bearing until a person confirms it |
| Exporting past a failing gate | `artifact-export`: the user may explicitly export unvalidated, watermarked |
| Recording a review, or accepting a check failure as an exception | `responsible-charge-review`: a review is an explicit, recorded, scoped action by a named person |
| Consenting to a dataset download | design decision D3: consent for that dataset, never on its own |

Over the MCP surface every one of these is a tool argument, and the agent fills in tool
arguments. An agent that reads 80 mm off a sketch, writes it into the spec, and then
sets `confirmed_by` to the engineer's name has produced a document that is
indistinguishable from one the engineer confirmed. Nothing in the protocol stopped it,
and the evidence bundle will say a person confirmed the value. That is the exact
laundering `responsible-charge-review` was written to prevent, reintroduced one layer
down.

The protocol now has the primitive. MCP elicitation (specification revision 2025-06-18,
extended with URL mode in 2025-11-25) lets a server ask the client to put a form in
front of the human and return accept, decline or cancel. Both target clients support it:
Claude Code from 2.1.76 (2026-03-14), with Elicitation hooks; Codex CLI from 0.119. Two
caveats are recorded and shape the design: Claude Code has shipped versions that did not
advertise the elicitation capability at initialization, and the agent's own hooks can
answer an elicitation on the person's behalf. So the server must handle a client that
cannot elicit, and must never treat an elicitation answer as proof of a person beyond
what the client can attest.

## What Changes

| Area | Change |
| --- | --- |
| Person-only decisions | The four decisions above are a closed list of person-only confirmations. No tool argument can supply one. |
| Elicitation first | When the client advertises elicitation, the server asks for the confirmation through it, in form mode, showing the value, its source and what confirming it means. Accept confirms; decline and cancel do not. |
| Fallback when the client cannot elicit | The tool refuses, naming the shell command that records the confirmation, or a confirmation file the person writes in the output folder: the value, its digest, the person, the date. The server reads the file; the agent cannot write it through any tool. |
| Channel is recorded | Every confirmation records its channel (elicitation through a named client and version, shell command, confirmation file) beside the person and date, and the disclosure in the bundle states it. A confirmation whose channel is an elicitation is reported as "answered through the client" rather than "confirmed by a person", because the server cannot see who answered. |
| Reviews over MCP | A review record and an exception acceptance follow the same path. The agent may prepare the dossier; only the person's channel can record the review. |

## Impact

- Deltas: `headless-automation` (ADDED), `input-ingestion` (ADDED),
  `evidence-attestation` (ADDED). Interacts with `responsible-charge-review`
  (unchanged: a review stays an explicit, scoped, recorded action), `artifact-export`
  (the override is one of the four), `sandbox-security` (consent is one of the four),
  `add-agent-context-intake` (draft confirmation is one of the four), and
  `add-interaction-quality` (a refusal names the one step that confirms).
- Affected code (when implemented): the MCP server in `src/anvilate/mcp.py` (capability
  check, elicitation requests, the person-only argument rule), the confirmation record,
  the disclosure.
- Explicitly out:
  - Any identity verification. The server records what the channel can attest and no
    more.
  - Signatures on confirmations beyond the existing optional attestation signing.
  - URL-mode elicitation (not needed; no hosted endpoint exists, by D1).
