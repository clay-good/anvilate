# Change: Give every MCP tool a subject, or say the server is not stateless

## Why

`modernize-mcp-server` published the tool contracts before the server, on the grounds that
the cheapest moment to change a tool surface is before a client has integrated against it.
Writing the request handler against those contracts found what that ordering is for:
**four of the eight published tools name nothing in their input to act on.**

| Tool | Input | What it returns |
| --- | --- | --- |
| `render_viewport` | a view name, a width | an image of — what? |
| `measure_geometry` | a query string | a measurement of — what? |
| `read_scorecard` | *nothing at all* | a scorecard |
| `export_artifact` | a format, a destination | an export of — what? |

Each is asking the server to remember what the last call produced. That is a session, and
the `headless-automation` requirement says the server operates **statelessly**. The
requirement's own worked scenario — "an agent calls build, then render, then validate" —
only makes sense if `render` can see what `build` made.

So the contradiction is in the requirement, not in the implementation, and no amount of
implementation resolves it. `anvilate.mcp.stateless_gaps()` derives the list from each
tool's declared `subject`, and `handle_request` refuses those four with the reason rather
than inventing an argument for them.

## What Changes

- `headless-automation`'s MCP requirement is modified to state **how each tool identifies
  what it acts on**, so that "stateless" and the tool list stop contradicting each other.

Three options were considered. The recommendation is the third.

**A. Every tool carries its whole subject.** `render_viewport(geometry, view)`,
`read_scorecard(scorecard)`. Exactly stateless, and the wire cost is the whole geometry on
every call — plus `read_scorecard(scorecard)` is a tool that returns its own argument,
which is not an operation.

**B. A session.** Per-connection state, as the tools are written today. It makes the
scenario work and gives up what statelessness bought: a client that reconnects is back
where it started, and two server processes behind a load balancer are not interchangeable.
It also contradicts the requirement as written, so it is a change to the requirement either
way.

**C. Content-addressed handles.** A tool returns a digest of what it produced; a later tool
takes that digest as its subject and resolves it from a content-addressed store. **This is
the recommendation.** The protocol surface stays stateless in the sense the spec means —
no per-connection memory, any instance can serve any call, a reconnect loses nothing — while
the payloads stay off the wire. It is not new machinery: Anvilate's evidence bundles are
already content-addressed, and the digest a bundle publishes is the same kind of name. And
it makes `read_scorecard(digest)` a real operation rather than an echo.

The cost of C is a declared dependency: the store has to exist, be reachable by every
instance, and have a stated retention policy. That is a real cost and it is stated rather
than hidden, which is the difference between a store and a session.

## Impact

- Affected specs: `headless-automation` (1 modified requirement).
- Affected code: `anvilate.mcp` — the four tools' input schemas and their `subject`
  declarations; `stateless_gaps()` empties itself as each is given one.
- No client has integrated against these contracts, which is why this is cheap now.
