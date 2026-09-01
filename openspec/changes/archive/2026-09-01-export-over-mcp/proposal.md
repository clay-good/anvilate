# Change: Let `export_artifact` return the one artifact a spec alone can produce

## Why

`export_artifact` was refused, and until the subjects landed the reason was that it named
nothing to act on. That was fixed: it takes a subject handle like every other tool. What was
left was a smaller and sharper question, and the refusal stated it.

**The evidence bundle needs no geometry.** `anvilate export` produces it from a spec file:
screen the spec, wrap the card in `BundleSections`, render. Given a handle, the MCP tool can
run the same three lines. A QIF results file and a DXF genuinely need built geometry and
stay refused.

So the operation was implementable and what stopped it was not code:

**The tool wrote a file to a path the caller named.** `export_artifact`'s published output
was `{format, path, sha256}` and its input carried a `destination`. The CLI gets that path
from a user typing it into their own shell. An MCP client is whatever the user connected the
server to, and "write this file here" is a capability, not a detail.

## What Changes

**Answered C: the tool returns the bundle and writes nothing.** Three shapes were on the
table — A, write where the caller says; B, write under a declared root; C, return the
document. C grants no capability at all: the tool publishes no `destination`, names no path,
and creates no file. A client that wants one saves what it was handed. A and B each asked an
operator to decide how far to trust an MCP client with the server's filesystem, and C asks
nobody anything. It is also the ruling already made for subjects one change earlier, applied
to the same question a second time.

Concretely:

| | before | after |
|---|---|---|
| input | `subject`, `format`, `destination` | `subject`, `format` |
| output | `format`, `path`, `sha256` | `format`, `bundle`, `sha256` |
| `sha256` names | the file written | the bundle's own canonical JSON |
| dispatched | no | yes, for `evidence_bundle` |

**The subject is a scorecard handle, not a spec handle.** A bundle is a document about a
screening result and `BundleSections` takes exactly that. Re-screening from a spec would be a
second answer to a question the client already has an answer to, and against tables that may
have moved it can disagree with the card in hand.

**Two of the three published formats are still refused, and now per format rather than per
tool.** `dxf` and `qif` wait on built geometry. The handler reads the CLI's own
`_UNBUILT_ARTIFACTS`, so the two surfaces cannot state different reasons for the same gap,
and the refusal is TOOL_UNAVAILABLE rather than INVALID_PARAMS — an unbuilt operation is not
an argument the caller can fix.

**One correction to this change's own draft.** The delta first said a failing card is refused
an export. That was wrong, and the other surface proves it: `anvilate export` prints the
bundle for a card that does not pass and reports the verdict in its exit code. An evidence
bundle is the evidence a part failed as much as the evidence it passed, and `artifact-export`
gates *CAD artifacts* — a DXF somebody cuts from — not the document that says what happened.
The gate is discharged here by the bundle carrying `SCREENING_DISCLAIMER` unconditionally and
stating its own status, which is what the watermark rule asks of it. Written down because a
scenario that survives into an archived spec is one somebody implements.

## Impact

- Affected specs: `headless-automation`.
- Affected code: `anvilate.mcp` — the tool contract, one handler, one new refusal class
  (`_Unavailable`, so a handler can reach TOOL_UNAVAILABLE), and `export_artifact` leaving
  `_UNBUILT`.
- Affected tests: `tests/test_surface_parity.py` loses its one divergence and gains a
  by-value comparison of the two bundles; `tests/test_export_gate.py` asks its gate-parity
  question per published format instead of through a single `backing` symbol.
