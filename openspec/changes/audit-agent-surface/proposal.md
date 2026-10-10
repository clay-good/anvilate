# Change: Audit the agent surface — fewer, clearer tools that work the same in Claude Code and Codex

## Why

Anvilate will be adopted if an engineer's agent gets a correct part on the first try, in
two or three calls, on the client they already use. The surface grew one tool and one flag
at a time, across many sessions, each correct on its own. Nobody has gone through all of it
at once, as an agent meets it.

What is known to be rough today:

- **Eight MCP tools, shaped by the pipeline's stages rather than by what a user asks for.**
  A simple request takes compile, validate, build, render and export as separate calls.
  One of the eight (`run_fea_validation`) can only ever answer "not evaluated", because no
  solver ships. Both Anthropic's and OpenAI's tool guidance says the same thing: a few
  workflow-level tools, small responses, errors that say what to do.
- **Measured once, on one client.** The agent-driving measurement ran on Claude Code only.
  Codex has a 60-second tool timeout, truncates by token budget, and passes only
  structured content to the model when a result has both; none of that has been tested.
- **Client limits are met by luck.** Claude Code cuts tool descriptions and server
  instructions at 2,048 characters, silently.
- **Install is `git clone`.** There is no `pip install anvilate`, so the first step of
  adoption is the hardest one.
- **Nine CLI commands, sixty-two docs pages and nearly five hundred examples** with no
  single pass over naming, defaults, overlap and what a newcomer reads first.

This is an audit with a defined end state, not a rewrite. It can run as its own session.

## What Changes

| Area | End state |
| --- | --- |
| Tool set | The smallest set of workflow-level tools that completes the documented journeys, each named for what the user wants. Tools that cannot produce a result are removed. The new set is proposed from measurements at the end of the audit, as its own delta, because renaming a tool is a breaking change. |
| Golden paths | Named journeys (check a described part; build and show it; export it; check a part against a folder of context; build a combination) each complete in a stated number of calls on both clients. |
| Two clients, measured | The same task corpus runs on Claude Code and Codex. Results are published per client and version, and a regression on either blocks a release. |
| Client limits as gates | Every description and the server instructions fit the shortest client limit; every result fits the size budget; every golden-path call fits the time limit. |
| Errors an agent can act on | Every refusal names the field, the reason and a valid example, and never suggests a value that is less safe than the one refused. |
| Install | `pip install anvilate` and a one-line `uvx` launch for the MCP server, with the geometry kernel included in the default install. |
| CLI | Every command, flag and default reviewed for overlap and naming; one table of what each is for. |
| Performance | The responsiveness budget extended to every tool and command, with the slowest five profiled and improved or justified. |
| Docs | A newcomer reaches a first part from the README alone; every other page is reachable from one index by task; pages that no longer describe the product are removed. |

## Impact

- Affected specs: `headless-automation` (ADDED), `onboarding` (ADDED), `benchmarking`
  (ADDED), `documentation` (ADDED).
- Sequenced after `simplify-visual-output` (which fixes how results are returned) and
  alongside the catalog and context changes, whose new tools it reviews before they ship.
- Affected code (when implemented): `anvilate.mcp` tool catalog and instructions, the
  agent skill, the measurement harness (a Codex runner), packaging and release, CLI help,
  docs.
- Explicitly out: clients other than Claude Code and Codex; any hosted service; changing
  what the checks compute.
