# Change: MCP server on the 2026-07-28 protocol — typed results, tasks, registry

## Why

The MCP 2026-07-28 release (final July 28, 2026 — RC:
https://blog.modelcontextprotocol.io/posts/2026-07-28-release-candidate/) restructures the
protocol in ways that fit Anvilate exactly: stateless operation, full JSON Schema 2020-12
for tool input/output schemas (Anvilate's `$ref`-heavy Spec IR schema can be the tool
contract directly), rich `structuredContent` results, a Tasks extension for long-running
work (the future FEA tier), and deprecation of server-side sampling — external validation
of the LLM-at-the-edges architecture. The official registry (~9,650 servers,
https://github.com/modelcontextprotocol/registry) is now how clients discover servers.

Prior art shows the winning agent pattern: build123d-mcp's tight
build-render-measure-repair loop with images and measurements in tool results
(https://github.com/pzfreo/build123d-mcp). No server in the registry offers *validated
engineering checks with citations* — an empty niche.

## What Changes

- `headless-automation`'s MCP requirement is modernized: target the 2026-07-28 protocol,
  stateless; tool contracts generated from the same JSON Schemas that define the Spec IR
  and scorecard; results returned as `structuredContent` plus preview images where visual
  feedback helps; no dependence on deprecated protocol features (sampling).
- Added: long-running validation runs exposed via the Tasks extension (progress,
  cancellation); publication to the official MCP registry per release.

## Impact

- Affected specs: `headless-automation` (1 modified, 2 added requirements).
- Affected code (when implemented): the MCP server component (not yet built — this
  changes its target before code exists, the cheapest possible time).
- The existing "MCP inherits all gates" rule is unchanged and restated in the modified
  requirement.
