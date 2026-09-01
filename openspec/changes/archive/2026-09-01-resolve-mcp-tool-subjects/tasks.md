# Tasks: Give every MCP tool a subject

## 1. Decide

- [x] 1.1 Choose between carrying the whole subject (A), a session (B), and
      content-addressed handles (C). **Answered: C**, by the user, on 2026-09-01. The
      deciding arguments are the ones the proposal states: the protocol surface stays
      stateless in the sense the spec means — any instance serves any call, a reconnect
      loses nothing — while whole payloads stay off the wire, and `read_scorecard(handle)`
      is a real operation where `read_scorecard(scorecard)` would be an echo.

## 2. Contracts

- [x] 2.1 `render_viewport`, `measure_geometry`, `read_scorecard` and `export_artifact` each
      take a required `subject`, declared on the `ToolDefinition`. `stateless_gaps()` emptied
      itself as they landed, exactly as the derivation promised — no edit anywhere else.
- [x] 2.2 What a client pinned to the old surface is owed, recorded on
      `docs/mcp-tool-contracts.md`: the four inputs gained a *required* property and two
      outputs gained one, so it is a breaking change to the tool surface. No client has
      integrated, which is what made it cheap, and an old-shaped call gets `-32602` naming
      the missing `subject` rather than a silent misread.

## 3. Implementation

- [x] 3.1 `anvilate.store` — the content-addressed store, with all three costs stated rather
      than assumed: **where it lives** (`$ANVILATE_SUBJECT_STORE`, else `subjects/` under the
      dataset cache root), **who can reach it** (a filesystem claim, not a network one — every
      instance is a process on one machine unless an operator points several at one directory),
      and **retention** (nothing evicts anything; a removed entry makes a handle stop
      resolving, and there is no path by which a missing entry becomes a *wrong* answer).
- [x] 3.2 `read_scorecard` is dispatched: `run_validation` publishes the card it screened and
      returns the handle, and `read_scorecard(handle)` reads it back. `compile_spec` publishes
      its compiled document the same way. The other three are refused with what they wait on
      — built geometry for two, and for `export_artifact` the bundle inputs (subjects, an
      environment BOM, an AI disclosure) that a tool call does not carry.

## Status

Complete. `examples/mcp_server_session.py` drives the loop against a real subprocess in two
rounds, because the second depends on the first — which is the difference between a session
and a transcript, and the thing a handle buys.
