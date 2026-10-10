# Design decisions

Decisions that settle a question for good, so it is not reopened by the next contributor or
the next agent session. Each says what was decided, why, what is therefore *not* built, and
which test holds it.

## D1. Anvilate is fully local. Nothing is hosted.

**Decided 2026-10-08.** Anvilate is downloaded from its GitHub repository and run on the
user's own machine. There is no Anvilate website, domain, server, account or hosted
endpoint, and none is planned.

- **Identifiers are URNs, never URLs.** Schema `$id`s are
  `urn:anvilate:schema:<name>:<version>`, the attestation predicate is
  `urn:anvilate:attestation:screening:v1`, and the 3MF namespace is `urn:anvilate:3mf`. A URL
  invites a client to fetch it, and whoever registered that domain would answer. A URN names
  a document without saying where to get it. They were `https://anvilate.dev/...` until this
  decision, a domain that never existed; `anvilate verify` still accepts the old predicate
  name so earlier envelopes verify.
- **Not built:** any hosted service, web API, telemetry, update check, or remote schema
  registry.
- **Held by:** `test_no_published_identifier_is_a_location` (tests/test_mcp.py) and the
  headless-automation requirement "The MCP server is local software, not a hosted service".

## D2. MCP only: the user's agent is the language model.

**Decided 2026-10-08.** Anvilate runs no language model. It holds no API key, starts no
inference, and ships no model adapter. The user's own agent (Claude Code, Claude Desktop,
Cursor, or any MCP client) drives Anvilate's local stdio MCP server: the agent writes the
spec, and Anvilate validates it, screens it, and refuses what is wrong.

- **Why:** an engineer who uses an AI tool already has one, with a model they chose and pay
  for. Asking them to manage a second API key, or download and run a multi-gigabyte model,
  is more work for a worse result. Anvilate's value is the deterministic, cited checking,
  which is the same whichever model wrote the spec.
- **What helps the agent instead:** the MCP `initialize` result carries `instructions`: the
  workflow, the rules for stating a requirement, and every material, component and element
  identifier, generated from the bundled databases. The rules came from running a real local
  model (qwen2.5:14b) before this decision: given only the schema, it wrote a stated minimum
  safety factor into `max_safety_factor`, dropped the load, spelled `ASTM-A36` as
  "ASTM A36", invented a hole pattern, and named no element.
- **Not built:** bring-your-own-key cloud models (Anthropic, OpenAI, Google), local model
  runtimes (Ollama, llama.cpp), and any CLI command that calls a model. The Ollama and
  llama.cpp adapters were removed. The model-independent scoring in
  `anvilate.compilation` stays, because it grades a spec whoever wrote it.
- **Without an agent:** write the spec in YAML and run `anvilate check`. Every check works
  with no AI at all.
- **Held by:** `test_only_explicit_transports_import_a_network_client`
  (tests/test_air_gapped.py, which allows a network client only in `anvilate.fetch`),
  `test_initialize_hands_the_agent_its_rules_and_the_live_catalogue` (tests/test_mcp.py),
  and the intent-compilation requirement "The user's agent is the model".

## D3. Consented dataset downloads are allowed.

**Decided 2026-10-08.** `anvilate.fetch` may download a dataset from its publisher (the AISC
shapes workbook, a benchmark index) when, and only when, the user consents for that dataset.
Each download is pinned by SHA-256, verified on download and on every read, cached locally,
and attributed. After one download everything works offline. This is the only network code in
the package, and it never runs on its own.

- **Held by:** `test_the_one_network_capable_path_refuses_before_it_reaches_the_transport`
  and tests/test_fetch.py.

## D4. Tool definitions carry their schemas.

**Decided 2026-10-08.** Each MCP tool definition embeds, under `$defs`, every published
schema it references, so a client validating a tool's input or output needs nothing beyond
the definition it was handed. The cost is a larger `tools/list` reply (about 303 KB rather
than 11 KB), accepted in exchange for schemas that resolve offline in every client.

- **Held by:** `test_every_tool_schema_compiles_offline_from_its_own_definition`
  (tests/test_mcp.py) and the `anvilate doctor` MCP server check.

## D5. No interface of our own: a picture, files, and the user's CAD.

**Decided 2026-10-09.** Anvilate is driven by the user's agent, so it ships no web app, no
server and no viewer. What it produces is a rendered image the agent can see, files the
engineer can open, and exchange formats (STEP, DXF, 3MF) for the CAD system they already
own. Rotating, sectioning and measuring a part is that CAD system's job. The workbench
specification and the `view --3d` viewer were removed.

Two consequences are in the code:

- **A render is an image and one line of text, with no structured content.** Claude Code
  and Codex both pass only `structuredContent` to the model when a result carries it beside
  an image, so the picture never arrived. `render_viewport` publishes no output schema.
- **The MCP server writes into one output folder, named when it starts**
  (`anvilate-mcp --out DIR`, default `./anvilate-out`). No tool takes a destination path,
  and a CAD file never passes through the model. This replaces the earlier ruling that the
  export tool writes nothing; the reason behind that ruling (a path a caller names is a
  capability) still holds, because no caller names one.

- **Held by:** tests/test_mcp_outputs.py, `test_no_tool_pairs_an_image_with_structured_content`
  (tests/test_mcp.py), and a recorded session per client under
  `tools/client-checks/results/` in which the model answers a question only the image can.
