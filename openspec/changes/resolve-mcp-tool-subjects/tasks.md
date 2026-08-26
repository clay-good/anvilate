# Tasks: Give every MCP tool a subject

## 1. Decide

- [ ] 1.1 Choose between carrying the whole subject (A), a session (B), and
      content-addressed handles (C). The proposal recommends C and states what it costs.
      **This is the blocking task**: the four schemas cannot be fixed until it is answered,
      and answering it wrong is expensive once a client has integrated.

## 2. Contracts

- [ ] 2.1 Give `render_viewport`, `measure_geometry`, `read_scorecard` and
      `export_artifact` a required subject property, and declare it on each
      `ToolDefinition`. `stateless_gaps()` empties itself as they land — it is derived, so
      nothing else has to be edited.
- [ ] 2.2 Bump the tool-surface version and record what a client pinned to the old one is
      owed. No client has integrated, which is what makes this cheap; that fact has a
      shelf life.

## 3. Implementation (follows the decision)

- [ ] 3.1 If C: the content-addressed store — where it lives, who can reach it, and its
      retention policy, stated rather than assumed.
- [ ] 3.2 Dispatch the tools that are backed once they have a subject to act on.

## Status

Not started. The contradiction is recorded and enforced today:
`anvilate.mcp.stateless_gaps()` derives the four from their declarations and
`handle_request` refuses them with the reason, so nothing can quietly serve one by
guessing. The decision in 1.1 is a design choice about what Anvilate's MCP surface *is*,
and it is the user's to make.
