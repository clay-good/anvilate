# Tasks: The bundle carries its spec

## 1. Decide

- [x] 1.1 Choose between a second handle (A), a paired record behind one handle (B), and the
      spec digest alone (C). **Answered B.** A makes reproducibility depend on how a client
      was written; C is excluded by the requirement's own "only the bundle".

## 2. Implementation

- [x] 2.1 `BundleSections.spec`, carried by both renderings — pasteable YAML in the text
      form, the dumped document in the JSON form, and `null` rather than absent so a
      consumer can tell "no spec" from "a key I did not look for". Out of the roll-up, which
      is hashed into signed attestations.
- [x] 2.2 Both surfaces supply it: the CLI from the document it loaded, MCP from the
      `{spec, scorecard}` record `run_validation` publishes.
- [x] 2.3 Parity: the bundle a spec produces at the shell and over MCP is identical, held by
      value over the standing hostile corpus in `tests/test_surface_parity.py`.
- [x] 2.4 The requirement's own scenario as a test: screen, export, **discard the spec**,
      rebuild it from the bundle, re-screen, assert the same card. Plus the text-front-door
      half — the parser reads back what the renderer wrote, and the block is nested under its
      heading so the document says where the spec ends.

## Status

Shipped. Four mutations kill the reproducibility tests (either surface dropping the spec, the
record publishing a different one, the rendered block losing its indent) and three kill the
record-shape tests.
