# Tasks: Person confirmation

Affects the MCP server in `src/anvilate/mcp.py` and the evidence disclosure.

## 1. The closed list

- [x] 1.1 Person-only confirmations enumerated: draft-value confirmation, unvalidated
      export, review or exception record, dataset consent
- [x] 1.2 No tool input schema carries a field that supplies one; CI gate over the catalog

## 2. Elicitation

- [x] 2.1 Read the MCP elicitation specification (2025-06-18 and the 2025-11-25 revision)
      and record the request and result shapes
- [x] 2.2 Capability check at initialization; form-mode request showing value, source and
      consequence; accept confirms, decline and cancel do not
- [ ] 2.3 A recorded session per target client under `tools/client-checks/results/` in
      which the form reaches the person

## 3. Fallback and record

- [x] 3.1 Refusal naming the shell command and the confirmation-file form when the client
      cannot elicit
- [x] 3.2 Confirmation file: value, digest, person, date; read by the server, unwritable
      by any tool
- [x] 3.3 Channel on every confirmation; disclosure wording per channel
- [x] 3.4 A docs page for person confirmation: what the agent can and cannot confirm
