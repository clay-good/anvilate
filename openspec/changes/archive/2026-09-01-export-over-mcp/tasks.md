# Tasks: Export over MCP

## 1. Decide

- [x] 1.1 Choose between writing where the caller says (A), writing under a declared root
      (B), and returning the bundle rather than writing it (C). **Answered C**: the tool
      returns the document and writes nothing, which is the only one of the three that
      grants no capability and asks no operator for a policy.

## 2. Implementation (follows the decision)

- [x] 2.1 Dispatch `export_artifact` for `evidence_bundle`: resolve the scorecard handle,
      `BundleSections`, return `{format, bundle, sha256}`. QIF and DXF stay refused, per
      format rather than per tool, from the CLI's own `_UNBUILT_ARTIFACTS`.
- [x] 2.2 The export gate on the same terms as every other surface. Two halves, because the
      formats differ: the CAD exporters take a mandatory `authorization` and are not wired
      here, and the bundle carries `SCREENING_DISCLAIMER` unconditionally and states its own
      verdict. There is no override on this surface either way.
- [x] 2.3 Parity: the same spec exported at the shell and over MCP produces the same bundle
      document, compared by value in `tests/test_surface_parity.py`.

## Status

Shipped. `anvilate.mcp._UNBUILT` no longer names this tool, and the census test that holds
that map against the dispatch table is what would catch a stale refusal left behind.
