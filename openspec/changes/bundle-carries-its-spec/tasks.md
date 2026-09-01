# Tasks: The bundle carries its spec

## 1. Decide

- [ ] 1.1 Choose between a second handle (A), a paired record behind one handle (B), and the
      spec digest alone (C). **This is the blocking task**, and it is the same shape as the
      one `export-over-mcp` answered: the CLI can do it today and the MCP contract is what
      needs a ruling.

## 2. Implementation (follows the decision)

- [ ] 2.1 `BundleSections` carries the spec, and both renderings show it.
- [ ] 2.2 Both surfaces supply it, by whichever route A/B/C names.
- [ ] 2.3 Parity: the bundle a spec produces at the shell and over MCP stays identical, the
      way `tests/test_surface_parity.py` already holds the scorecard half.
- [ ] 2.4 The requirement's own scenario as a test: screen a spec, take **only** the bundle,
      rebuild the spec from it, re-screen, and assert the same card comes back. That is the
      check nothing in this repo can currently make.

## Status

Not started. The scorecard half shipped first because it needed no decision; this is what is
left of the requirement, and it is written down rather than left as a silence in a page.
