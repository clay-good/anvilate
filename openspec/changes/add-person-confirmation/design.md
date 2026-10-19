# Design notes: Person confirmation

Implemented on 2026-10-19. The protocol shapes below were read from the specification
pages the same day.

## Wire shapes (task 2.1)

**2026-07-28** (https://modelcontextprotocol.io/specification/2026-07-28/client/elicitation,
`basic/patterns/mrtr`). Server-initiated requests are gone. A `tools/call` the server cannot
finish without the person returns an `InputRequiredResult`:

```json
{"resultType": "input_required",
 "inputRequests": {"draft-0": {"method": "elicitation/create",
   "params": {"mode": "form", "message": "...", "requestedSchema": {"type": "object", "...": "..."}}}},
 "requestState": "<opaque>"}
```

The client retries with a new JSON-RPC id and `params.inputResponses` (same keys, each an
`ElicitResult`: `{"action": "accept" | "decline" | "cancel", "content": {...}}`) and the
exact `requestState`. Capabilities arrive per request in
`_meta["io.modelcontextprotocol/clientCapabilities"]`; `{"elicitation": {}}` means form
mode. `requestState` is attacker-controlled input: it must be integrity-protected when it
influences business logic, and a server must not send an input request type the client did
not declare.

**2025-11-25 and earlier** (https://modelcontextprotocol.io/specification/2025-11-25/client/elicitation).
The client declares `capabilities.elicitation` in `initialize`. The server sends
`elicitation/create` as a JSON-RPC request with its own id while the client's call is in
flight, and the client answers with a JSON-RPC response whose `result` is the same
`ElicitResult`.

## Decisions

| Question | Decision | Why |
| --- | --- | --- |
| Where the handlers ask | Only in the 2026-07-28 shape, by raising `_InputRequired` from `handle_request` | `handle_request` stays a pure function of one request, as the stateless server requires |
| Older clients (Claude Code negotiates 2025-11-25) | `serve_stdio` remembers the elicitation capability and client identity from `initialize`, sends each input request as a server request, holds any other message that arrives meanwhile, and retries the call itself | The client sees one response to one call, as its revision expects; the handlers never learn which revision asked |
| `requestState` | Base64 JSON of the tool, the kind of question, the subjects asked by key, and an expiry, sealed with HMAC-SHA256 under a per-process random key | Verification failure, expiry or another tool's state reads as no answer, so the person is asked again; nothing worse is possible |
| Where a confirmation is kept | A record keyed by the content digest of what it confirms, under the dataset cache root; declines beside it | Any instance reads it; no call is remembered |
| How the channel travels | `SourceReference.confirmed_via` and `confirmed_through` (Spec IR 1.22.0), stamped from the record, never taken from the document | The spec, the card line and the bundle all carry it, and a reviewer holding only the bundle sees it |
| What a channel attests | Only an interactive terminal is recorded as attesting a person. An elicitation reads "answered through" the named client | A client's hooks can answer a form; the server cannot see who did |
| The file channel | Read from `<output>/confirmations/*.json`; the channel is decided by the folder, never by the file's content | Anything that can write the folder could write any claim |
| An agent-written `confirmed_by` over MCP | Refused by field name unless a record confirms the same value under the same name, channel and client | The document arrives from the agent; the record is what a person's channel left |
| Unvalidated export over MCP | Asked through a form when the client elicits; otherwise refused naming `anvilate build --unvalidated` and the file form with the subject digest | It was "this surface grants no override". It still grants none of its own: the person does |
| Reviews and dataset consent | On the closed list and held by the catalog gate; no MCP tool performs either, so no form is needed yet | A tool that adds one inherits the gate |
| The disclosure | A "person-only confirmations" block in the rendered evidence bundle, listing each agent reading with its channel and whether any confirmation is attested to a person | The attestation predicate's v1 wire shape is pinned for consumers and is not changed; the bundle document carries the spec with its channels |

## Open

Task 2.3, a recorded session per target client in which the form reaches a person, needs a
human answering a real form in Claude Code and in Codex. It is left open until someone
records it with `tools/client-checks/`. Two reports, both from users and unconfirmed, are
why it matters: one says some Claude Code builds did not advertise elicitation at
`initialize`, and the other says Claude Code 2.1.237 did not advertise URL-mode elicitation
under the 2026-07-28 revision. If a target client advertises nothing, the fallback refusal
is what it gets, and the session should show that.
