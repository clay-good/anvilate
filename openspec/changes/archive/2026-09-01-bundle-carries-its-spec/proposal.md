# Change: Put the spec in the bundle, so "re-run it from this alone" becomes true

## Why

`artifact-export`'s evidence-bundle requirement asks for "the spec, the scorecard with
thresholds and measured values, ... sufficient for an independent engineer to reproduce the
run", and its scenario is an engineer who receives **only the bundle** and obtains the same
scorecard.

The scorecard half landed first: both export surfaces emit `render_document()` /
`to_document_dict()`, which carry every check with its detail and its clause. Before that
they emitted the layer roll-up, which said `3 run, 1 failing` and named nothing.

The spec half was still missing, and it was not a small gap. **A bundle named the verdicts
and not the inputs they were computed from.** A reviewer could see that `net tension` passed
at 4.4 and could not see the load, the thickness or the material it passed on, so the
scenario was not merely untested — it was false, and there was nothing in the repo that
could have shown it.

## What Changes

**Answered B: the handle names the pair.** At the shell the spec is in hand, so the CLI
passes it and that half needed no ruling. Over MCP `export_artifact` receives only a subject
handle, so `run_validation` publishes `{spec, scorecard}` under one handle of kind
`screening`, and both tools that read a screening result go through one resolver.

Why not the other two:

**A, an optional second `spec` handle on the export call**, makes a bundle reproducible or
not depending on how a client happened to be written. A bundle that is *sometimes*
reproducible is one a reviewer cannot rely on, and it would have broken the by-value parity
between the two surfaces that had just been established. Under B there is no call sequence
that produces the lesser bundle: the screen that computed the verdicts publishes the document
they were computed from.

**C, the spec digest alone**, is ruled out by the requirement's own words. Fetching the spec
by digest from somewhere else is exactly what "only the bundle" excludes.

Concretely:

| | before | after |
|---|---|---|
| `BundleSections` | scorecard, layers | plus `spec: DesignSpec \| None` |
| the exported document | roll-up + every check | plus the spec, as pasteable YAML |
| the MCP handle names | a scorecard | `{spec, scorecard}`, kind `screening` |
| the roll-up (`to_json_dict`) | unchanged | **unchanged** — it is hashed into signed attestations |

**The scenario is now a test rather than a sentence.** Screen a spec, export it through each
surface, discard the original, rebuild the spec out of the bundle, re-screen it, and require
the card to come back identical. A second test asks the question that matters for a text-first
tool: the YAML is pulled back out of the *rendered* bundle and screened, so the claim is that
`anvilate check` reads what `anvilate export` wrote — not merely that pydantic can rebuild its
own dump.

**A bundle carrying no spec says so**, in a line of its own, on the rule the assumptions block
already follows: a bundle that cannot be re-run and one whose author forgot the section must
not read the same.

## Impact

- Affected specs: `artifact-export`.
- Affected code: `anvilate.bundle` (one field, one rendering block), `anvilate.cli` (one
  argument), `anvilate.mcp` (the published record, one shared resolver, one refusal).
- **Breaking for a stale handle.** A handle published before this change resolves as a
  `scorecard` and is refused, naming both kinds and saying to call `run_validation` again.
  Nothing in the store evicts anything, so such handles are still on disk; the store's
  guarantee is that a handle gives a right answer or none, and this keeps it.
- `spec_digest` on the attested predicate is unaffected, and so is every existing
  attestation digest: the spec is in the exported document and not in the roll-up.
