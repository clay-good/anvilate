# Change: Agent skill surface — teach coding agents to use Anvilate correctly

## Why

Anvilate's MCP server exposes what an agent *can* call. It does not convey what an
engineer would consider correct use: retrieve standard dimensions rather than recalling
them, read the scorecard before claiming success, never present a screening result as
certified, never export past a failing gate. An agent with tool access and no procedural
guidance will do all four wrong, and the resulting artifact still carries Anvilate's
evidence bundle.

Capability packaging for agents standardized during 2026: SKILL.md was open-standardized
in December 2025 and now has compatible implementations across most major agent products,
while AGENTS.md became the de facto repository-instruction convention read natively by
nearly all coding agents. Vendors increasingly ship first-party skills next to their MCP
servers. Anvilate should too — it is the cheapest available lever on correct third-party
use, and it is the only mechanism that reaches agents whose operators never read the
documentation.

This also gives the agent-driving evaluation in `extend-benchmarking-agent-evals`
something concrete to measure: does shipping the skill measurably improve the funnel?

## What Changes

- `headless-automation` (ADDED): Anvilate ships a versioned first-party agent skill in
  the open SKILL.md convention plus a repository-convention file, covering the
  doctrine-bearing workflows; the skill is documentation, never a privilege — it grants
  nothing the tool surface does not already allow, and every gate applies identically
  whether or not it was loaded; and skill content is CI-verified against the real tool
  surface so it cannot drift into describing tools that no longer exist.

## Impact

- Affected specs: `headless-automation` (one ADDED requirement; the MCP requirement and
  its "inherits all gates" rule are unchanged, and `modernize-mcp-server` may land
  independently in either order).
- Affected code (when implemented): a skill directory shipped in the distribution, plus a
  CI check binding skill examples to the tool schemas and the documentation examples
  harness.
- Out of scope: agent-specific proprietary formats, and any behavior that varies by which
  client is connected.
