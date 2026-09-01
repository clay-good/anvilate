# Change: Put the spec in the bundle, so "re-run it from this alone" becomes true

## Why

`artifact-export`'s evidence-bundle requirement asks for "the spec, the scorecard with
thresholds and measured values, ... sufficient for an independent engineer to reproduce the
run", and its scenario is an engineer who receives **only the bundle** and obtains the same
scorecard.

The scorecard half landed: both export surfaces now emit `render_document()` /
`to_document_dict()`, which carry every check with its detail and its clause. Before that
they emitted the layer roll-up, which said `3 run, 1 failing` and named nothing — a document
called evidence with no evidence in it.

The spec half is still missing, and the reason is a contract question rather than an
oversight. **A bundle names the verdicts and not the inputs they were computed from.** A
reviewer can see that `net tension` passed at 4.4 and cannot see the load, the thickness or
the material it passed on, so they cannot re-run anything.

## What Changes

Nothing until the question below is answered.

At the shell the spec is in hand: `anvilate export` loads the document before it screens, so
adding it to the bundle is one field. Over MCP it is not: `export_artifact` takes a
**scorecard** handle, deliberately — the bundle is a document about a screening result, and
taking a spec handle would mean re-screening and possibly disagreeing with the card the
client already holds.

Three shapes:

**A. A second handle.** `export_artifact` gains an optional `spec` subject, and a bundle
built with it carries the spec. Honest, and it makes the two surfaces' bundles differ by
whether the caller passed a second argument.

**B. `run_validation` publishes the pair.** The handle it returns names a record holding the
card *and* the spec it screened, so one handle carries both and `export_artifact` is
unchanged. The store's `kind` grows a third value; a handle to a bare scorecard stops being
what the export tool wants.

**C. The spec digest, not the spec.** The bundle carries `spec_digest` — which the attested
predicate already has — and the reviewer fetches the document by it. Smallest, and it makes
reproduction depend on having the spec by some other route, which is what the requirement's
"only the bundle" rules out.

## Impact

- Affected specs: `artifact-export` (what the bundle carries), and `headless-automation`
  under A or B.
- Affected code: `anvilate.bundle` (one field), `anvilate.cli`, `anvilate.mcp`, and under B
  `anvilate.store`.
- The `spec_digest` on the attested predicate is unaffected either way.
