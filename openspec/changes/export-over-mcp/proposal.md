# Change: Let `export_artifact` write the one artifact a spec alone can produce

## Why

`export_artifact` is refused, and until the subjects landed the reason was that it named
nothing to act on. That is fixed: it takes a subject handle like every other tool. What is
left is a smaller and sharper question, and the refusal currently states it.

**The evidence bundle needs no geometry.** `anvilate export` produces it from a spec file:
screen the spec, wrap the card in `BundleSections`, render. Given a spec handle, the MCP tool
can run the same three lines. A QIF results file and a DXF genuinely need built geometry and
stay refused.

So the operation is implementable today. What stops it is not code:

**The tool writes a file to a path the caller names.** `export_artifact`'s published output
is `{format, path, sha256}` — it emits an artifact, and its input carries a `destination`.
The CLI gets that path from a user typing it into their own shell. An MCP client is whatever
the user connected the server to, and "write this file here" is a capability, not a detail.
The `Gate.WATERMARK` and `Gate.VALIDATION` rules the tool already declares govern *what* may
be written and say nothing about *where*.

## What Changes

Nothing until the question below is answered. Three shapes were considered:

**A. Write where the caller says.** The tool behaves like the CLI: the destination is a path
and the server writes it. Simplest, and it grants an MCP client the ability to write a file
anywhere the server process can — including over something.

**B. Write under a declared root.** A configured export directory; a destination is resolved
inside it and a traversal outside is refused. Bounded, and it needs an operator to set the
root and a rule for what happens when they have not.

**C. Return the bundle instead of writing it.** The tool answers with the rendered bundle as
`structuredContent` and writes nothing; the client saves it if it wants a file. Statelessly
honest and it needs no filesystem trust at all — but it changes the published output schema,
and the tool stops "emitting an artifact" in the sense `emits_artifacts` and the watermark
gate mean.

## Impact

- Affected specs: none until the shape is chosen; A and B leave `headless-automation` as it
  is, C changes what the export tool returns.
- Affected code: `anvilate.mcp` — one dispatch entry and, for C, an output schema and a
  tool-surface bump.
- The export gate applies either way and there is no override on this surface: a card that
  does not pass is refused, not watermarked and written.
