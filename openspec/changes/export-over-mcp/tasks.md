# Tasks: Export over MCP

## 1. Decide

- [ ] 1.1 Choose between writing where the caller says (A), writing under a declared root
      (B), and returning the bundle rather than writing it (C). **This is the blocking
      task.** The operation is three lines the CLI already runs; what it needs is a decision
      about whether an MCP client may name a path the server writes to.

## 2. Implementation (follows the decision)

- [ ] 2.1 Dispatch `export_artifact` for `evidence_bundle` from a spec handle: resolve, screen,
      `BundleSections`, and whichever of A/B/C the answer names. QIF and DXF stay refused, and
      their reason stays geometry.
- [ ] 2.2 The export gate on the same terms as every other surface — a card that does not pass
      is refused rather than watermarked and written, and this surface grants no override.
- [ ] 2.3 Parity: the same spec exported at the shell and over MCP produces the same bundle
      document, held the way `tests/test_surface_parity.py` holds the screening halves.

## Status

Not started, and deliberately so. `anvilate.mcp._UNBUILT` states this reason in the refusal a
client receives, so the gap is visible from outside rather than only here.
